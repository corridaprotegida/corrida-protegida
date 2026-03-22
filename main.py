import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_js_eval import get_geolocation
from streamlit_autorefresh import st_autorefresh
from geopy.geocoders import Nominatim
import pandas as pd
import urllib.parse

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)
geolocator = Nominatim(user_agent="corrida_protegida_v5")

# Atualização automática a cada 5 segundos
st_autorefresh(interval=5000, key="global_refresh")

# --- FUNÇÕES DE APOIO ---
def play_notification_sound():
    audio_html = '<audio autoplay><source src="https://codeskulptor-demos.commondatastorage.googleapis.com" type="audio/mp3"></audio>'
    st.markdown(audio_html, unsafe_allow_html=True)

def get_coords(endereco):
    try:
        location = geolocator.geocode(endereco + ", Ponta Grossa, PR")
        return (location.latitude, location.longitude) if location else (None, None)
    except: return (None, None)

# --- ESTADO DE LOGIN ---
if "user_cpf" not in st.session_state:
    st.session_state.update({"user_cpf": None, "user_nome": None, "user_tipo": None, "last_order_count": 0})

def logout():
    if st.session_state.user_cpf:
        conn.table("usuarios").update({"logado": False}).eq("cpf", st.session_state.user_cpf).execute()
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

# --- LOGIN / CADASTRO ---
if not st.session_state.user_cpf:
    st.title("🛡️ CORRIDA PROTEGIDA")
    t1, t2 = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    with t2:
        tp = st.radio("Eu sou:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="reg_tp")
        n, c, s = st.text_input("Nome"), st.text_input("CPF"), st.text_input("Senha", type="password")
        pix = st.text_input("Chave PIX") if tp == "Sou Motorista" else ""
        if st.button("Finalizar Cadastro"):
            conn.table("usuarios").insert([{"tipo": tp, "nome": n, "cpf": c, "senha": s, "chave_pix": pix}]).execute()
            st.success("✅ Cadastrado!")
    with t1:
        tl = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista", "Administrador"], horizontal=True)
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
        st.sidebar.divider()
        perfil_ativo = st.sidebar.radio("🛠️ Modo Teste:", ["Administrador", "Sou Passageiro", "Sou Motorista"])
    st.sidebar.button("🚪 Sair", on_click=logout)

    # --- 1. VISÃO PASSAGEIRO ---
    if perfil_ativo == "Sou Passageiro":
        st.title("Painel do Passageiro 📍")
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        
        if res.data:
            c = res.data[0]
            st.info(f"Status: **{c['status']}**")
            # Mapa de trajeto duplo
            lat_o, lon_o = get_coords(c['ponto_origem'])
            lat_d, lon_d = get_coords(c['ponto_destino'])
            st.map(pd.DataFrame({'lat': [lat_o, lat_d], 'lon': [lon_o, lon_d]}))
            st.button("Cancelar ❌", on_click=lambda: conn.table("corridas").delete().eq("id", c['id']).execute())
        else:
            o, d = st.text_input("Origem"), st.text_input("Destino")
            v = st.number_input("Oferta (R$)", 5.0, value=15.0)
            if o or d:
                pts = []
                lo, no = get_coords(o); ld, nd = get_coords(d)
                if lo: pts.append({'lat': lo, 'lon': no})
                if ld: pts.append({'lat': ld, 'lon': nd})
                if pts: st.map(pd.DataFrame(pts))
            if st.button("SOLICITAR 🚀") and o and d:
                conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": o, "ponto_destino": d, "valor_total": v, "status": "Buscando"}]).execute()
                st.rerun()

    # --- 2. VISÃO MOTORISTA (TELA DIVIDIDA) ---
    elif perfil_ativo == "Sou Motorista":
        st.title("Painel do Motorista 🛣️")
        col_map, col_list = st.columns([2, 1]) # Mapa maior à esquerda

        loc = get_geolocation()
        if loc:
            lat_m, lon_m = loc['coords']['latitude'], loc['coords']['longitude']
            conn.table("corridas").update({"lat_motorista": lat_m, "lon_motorista": lon_m}).eq("motorista_nome", st.session_state.user_nome).eq("status", "Confirmada").execute()

        with col_list:
            st.subheader("🔔 Chamadas")
            corridas = conn.table("corridas").select("*").eq("status", "Buscando").execute()
            if len(corridas.data) > st.session_state.last_order_count: play_notification_sound()
            st.session_state.last_order_count = len(corridas.data)

            if not corridas.data: st.write("Aguardando...")
            for r in corridas.data:
                with st.expander(f"👤 {r['passageiro']} - R$ {r['valor_total']}", expanded=True):
                    st.write(f"🚩 {r['ponto_origem']} ➡️ {r['ponto_destino']}")
                    addr = urllib.parse.quote(r['ponto_destino'])
                    st.markdown(f'<a href="waze://?q={addr}&navigate=yes"><button style="width:100%; background-color:#33CCFF; color:white; border:none; padding:8px; border-radius:5px; font-weight:bold;">WAZE</button></a>', unsafe_allow_html=True)
                    if st.button(f"ACEITAR #{r['id']}", use_container_width=True):
                        conn.table("corridas").update({"status": "Confirmada", "motorista_nome": st.session_state.user_nome}).eq("id", r['id']).execute()
                        st.rerun()

        with col_map:
            st.subheader("Mapa de Trajetos")
            pontos_mapa = []
            # Adiciona Origem e Destino de TODAS as chamadas no mapa
            for r in corridas.data:
                lo, no = get_coords(r['ponto_origem'])
                ld, nd = get_coords(r['ponto_destino'])
                if lo: pontos_mapa.append({'lat': lo, 'lon': no})
                if ld: pontos_mapa.append({'lat': ld, 'lon': nd})
            
            if loc: pontos_mapa.append({'lat': lat_m, 'lon': lon_m}) # Posição do motorista
            if pontos_mapa: 
                st.map(pd.DataFrame(pontos_mapa), zoom=13)
            else: st.info("Ative o GPS ou aguarde chamadas.")

    # --- 3. VISÃO ADMINISTRADOR ---
    elif perfil_ativo == "Administrador":
        st.title("🛡️ Painel ADM")
        t_u, t_c = st.tabs(["Usuários", "Corridas"])
        with t_u:
            ud = conn.table("usuarios").select("*").execute()
            if ud.data: st.dataframe(pd.DataFrame(ud.data)[['nome', 'tipo', 'logado']])
        with t_c:
            cd = conn.table("corridas").select("*").neq("status", "Finalizada").execute()
            for ca in cd.data:
                st.write(f"ID {ca['id']} - {ca['passageiro']} | {ca['status']}")
                if st.button(f"Encerrar #{ca['id']}"):
                    conn.table("corridas").update({"status": "Finalizada"}).eq("id", ca['id']).execute()
                    st.rerun()
