import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_js_eval import get_geolocation
from streamlit_autorefresh import st_autorefresh
from geopy.geocoders import Nominatim # Para transformar texto em coordenadas
import pandas as pd
import urllib.parse

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")
conn = st.connection("supabase", type=SupabaseConnection)
geolocator = Nominatim(user_agent="corrida_protegida_app")

st_autorefresh(interval=5000, key="global_refresh")

# --- FUNÇÃO PARA PEGAR COORDENADAS DO TEXTO ---
def get_coords(endereco):
    try:
        location = geolocator.geocode(endereco + ", Ponta Grossa, PR") # Refina para sua cidade
        if location:
            return location.latitude, location.longitude
        return None, None
    except:
        return None, None

# --- ESTADO DE LOGIN ---
if "user_cpf" not in st.session_state:
    st.session_state.user_cpf = None
if "user_nome" not in st.session_state:
    st.session_state.user_nome = None
if "user_tipo" not in st.session_state:
    st.session_state.user_tipo = None

def logout():
    if st.session_state.user_cpf:
        conn.table("usuarios").update({"logado": False}).eq("cpf", st.session_state.user_cpf).execute()
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --- TELA DE ACESSO ---
if not st.session_state.user_cpf:
    st.title("🛡️ CORRIDA PROTEGIDA")
    t1, t2 = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    with t2:
        tp = st.radio("Eu sou:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="r_tp")
        n, c, s = st.text_input("Nome"), st.text_input("CPF"), st.text_input("Senha", type="password")
        pix = st.text_input("Chave PIX") if tp == "Sou Motorista" else ""
        if st.button("Finalizar Cadastro"):
            conn.table("usuarios").insert([{"tipo": tp, "nome": n, "cpf": c, "senha": s, "chave_pix": pix}]).execute()
            st.success("✅ Cadastrado!")
    with t1:
        tl = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista", "Administrador"], horizontal=True, key="l_tp")
        lc, ls = st.text_input("CPF", key="l_c"), st.text_input("Senha", type="password", key="l_s")
        if st.button("Acessar"):
            r = conn.table("usuarios").select("*").eq("cpf", lc).eq("senha", ls).eq("tipo", tl).execute()
            if r.data:
                u = r.data[0]
                st.session_state.update({"user_cpf": u['cpf'], "user_nome": u['nome'], "user_tipo": u['tipo']})
                conn.table("usuarios").update({"logado": True}).eq("cpf", u['cpf']).execute()
                st.rerun()

# --- PAINEL LOGADO ---
else:
    st.sidebar.write(f"👤 **{st.session_state.user_nome}**")
    perfil_ativo = st.session_state.user_tipo
    if st.session_state.user_tipo == "Administrador":
        perfil_ativo = st.sidebar.radio("Ver como:", ["Administrador", "Sou Passageiro", "Sou Motorista"])
    st.sidebar.button("🚪 Sair", on_click=logout)

    # --- 1. VISÃO PASSAGEIRO ---
    if perfil_ativo == "Sou Passageiro":
        st.title("Pedir Corrida 📍")
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        
        if res.data:
            c = res.data[0]
            st.info(f"Status: {c['status']}")
            # Mapa do Motorista vindo
            if c['status'] == "Confirmada" and c.get('lat_motorista'):
                st.map(pd.DataFrame({'lat': [c['lat_motorista']], 'lon': [c['lon_motorista']]}))
            st.button("Cancelar ❌", on_click=lambda: conn.table("corridas").delete().eq("id", c['id']).execute())
        else:
            origem = st.text_input("Onde você está?", placeholder="Ex: Terminal Uvaranas")
            destino = st.text_input("Para onde vamos?", placeholder="Ex: Rua Robalo 296")
            
            # MOSTRAR MAPA PRÉVIA (ORIGEM)
            if origem:
                lat_o, lon_o = get_coords(origem)
                if lat_o:
                    st.caption("📍 Localização identificada no mapa:")
                    st.map(pd.DataFrame({'lat': [lat_o], 'lon': [lon_o]}), zoom=14)
                else: st.warning("Endereço não localizado. Tente ser mais específico.")

            v = st.number_input("Sua oferta (R$)", 5.0, value=15.0)
            if st.button("SOLICITAR 🚀") and origem and destino:
                conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": origem, "ponto_destino": destino, "valor_total": v, "status": "Buscando"}]).execute()
                st.rerun()

    # --- 2. VISÃO MOTORISTA ---
    elif perfil_ativo == "Sou Motorista":
        st.title("Painel do Motorista 🛣️")
        
        # GPS REAL DO MOTORISTA
        loc = get_geolocation()
        if loc:
            lat_m, lon_m = loc['coords']['latitude'], loc['coords']['longitude']
            conn.table("corridas").update({"lat_motorista": lat_m, "lon_motorista": lon_m}).eq("motorista_nome", st.session_state.user_nome).eq("status", "Confirmada").execute()

        st.subheader("Chamadas Disponíveis")
        corridas = conn.table("corridas").select("*").eq("status", "Buscando").execute()
        
        for r in corridas.data:
            with st.container(border=True):
                st.write(f"👤 **{r['passageiro']}** | R$ {r['valor_total']:.2f}")
                st.write(f"🚩 De: {r['ponto_origem']} ➡️ {r['ponto_destino']}")
                
                # MAPA PARA O MOTORISTA VER A ORIGEM
                lat_p, lon_p = get_coords(r['ponto_origem'])
                if lat_p:
                    st.map(pd.DataFrame({'lat': [lat_p], 'lon': [lon_p]}), zoom=13)
                
                # WAZE
                addr = urllib.parse.quote(r['ponto_destino'])
                st.markdown(f'<a href="waze://?q={addr}&navigate=yes"><button style="width:100%; background-color:#33CCFF; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold;">🚀 ABRIR NO APP WAZE</button></a>', unsafe_allow_html=True)
                
                if st.button(f"Aceitar Corrida #{r['id']}", use_container_width=True):
                    conn.table("corridas").update({"status": "Confirmada", "motorista_nome": st.session_state.user_nome}).eq("id", r['id']).execute()
                    st.rerun()

    # --- 3. VISÃO ADMINISTRADOR ---
    elif perfil_ativo == "Administrador":
        st.title("🛡️ Painel ADM")
        users = conn.table("usuarios").select("*").execute()
        if users.data: st.dataframe(pd.DataFrame(users.data)[['nome', 'tipo', 'logado']])
