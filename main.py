import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_js_eval import get_geolocation
from streamlit_autorefresh import st_autorefresh
from streamlit_folium import st_folium
import folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import pandas as pd
import urllib.parse

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")
conn = st.connection("supabase", type=SupabaseConnection)

# Atualização automática (5s) para sincronizar motorista e passageiro
st_autorefresh(interval=5000, key="global_refresh")

# --- FUNÇÕES DE GEOLOCALIZAÇÃO ---
def get_coords(endereco):
    if not endereco: return None
    try:
        geolocator = Nominatim(user_agent="corrida_protegida_pg")
        # Forçamos a busca em Ponta Grossa para o seu teste
        location = geolocator.geocode(f"{endereco}, Ponta Grossa, PR")
        if location:
            return (location.latitude, location.longitude)
        return None
    except:
        return None

# --- ESTADO DA SESSÃO ---
if "user_cpf" not in st.session_state:
    st.session_state.update({"user_cpf": None, "user_nome": None, "user_tipo": None})

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
        tp = st.radio("Eu sou:", ["Sou Passageiro", "Sou Motorista"], horizontal=True)
        n, c, s = st.text_input("Nome"), st.text_input("CPF"), st.text_input("Senha", type="password")
        pix = st.text_input("Chave PIX") if tp == "Sou Motorista" else ""
        if st.button("Cadastrar"):
            conn.table("usuarios").insert([{"tipo": tp, "nome": n, "cpf": c, "senha": s, "chave_pix": pix}]).execute()
            st.success("Conta criada!")

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
    if st.sidebar.button("🚪 Sair"): logout()
    
    perfil = st.session_state.user_tipo

    # --- VISÃO PASSAGEIRO ---
    if perfil == "Sou Passageiro":
        st.title("Pedir Corrida 📍")
        
        # Verifica se já tem corrida ativa
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        
        if res.data:
            c = res.data[0]
            st.warning(f"Status: {c['status']}")
            if c['motorista_nome']: st.info(f"Motorista: {c['motorista_nome']}")
            
            # Mapa de Acompanhamento (Se confirmado, mostra motorista)
            m_view = folium.Map(location=[-25.0945, -50.1633], zoom_start=13)
            if c['lat_motorista']:
                folium.Marker([c['lat_motorista'], c['lon_motorista']], icon=folium.Icon(color='blue', icon='car', prefix='fa')).add_to(m_view)
            st_folium(m_view, width=700, height=300, key="map_view")
            
            if st.button("Cancelar Corrida"):
                conn.table("corridas").delete().eq("id", c['id']).execute()
                st.rerun()
        else:
            origem = st.text_input("De onde? (Ex: Terminal Uvaranas)")
            destino = st.text_input("Para onde? (Ex: Rua Robalo 296)")
            
            if origem and destino:
                coord_o, coord_d = get_coords(origem), get_coords(destino)
                if coord_o and coord_d:
                    dist = geodesic(coord_o, coord_d).km
                    valor = max(5.0, dist * 2.5) # R$ 2,50 por KM, mínimo 5 reais
                    
                    st.write(f"📏 Distância: {dist:.2f} km | 💰 Valor: R$ {valor:.2f}")
                    
                    # MAPA DE PREVISÃO
                    m = folium.Map(location=coord_o, zoom_start=14)
                    folium.Marker(coord_o, icon=folium.Icon(color='green')).add_to(m)
                    folium.Marker(coord_d, icon=folium.Icon(color='red')).add_to(m)
                    folium.PolyLine([coord_o, coord_d], color="blue").add_to(m)
                    st_folium(m, width=700, height=300, key="map_req")

                    if st.button("CONFIRMAR SOLICITAÇÃO 🚀"):
                        conn.table("corridas").insert([{
                            "passageiro": st.session_state.user_nome,
                            "ponto_origem": origem, "ponto_destino": destino,
                            "distancia_km": dist, "valor_total": valor, "status": "Buscando"
                        }]).execute()
                        st.rerun()

    # --- VISÃO MOTORISTA ---
    elif perfil == "Sou Motorista":
        st.title("Painel do Motorista 🛣️")
        
        # Envia localização GPS real para o banco
        loc = get_geolocation()
        if loc:
            lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
            conn.table("corridas").update({"lat_motorista": lat, "lon_motorista": lon}).eq("motorista_nome", st.session_state.user_nome).eq("status", "Confirmada").execute()

        corridas = conn.table("corridas").select("*").eq("status", "Buscando").execute()
        for r in corridas.data:
            with st.container(border=True):
                st.write(f"📍 {r['ponto_origem']} ➡️ {r['ponto_destino']}")
                st.write(f"💰 **R$ {r['valor_total']:.2f}** ({r['distancia_km']:.1f}km)")
                if st.button(f"Aceitar Corrida #{r['id']}", use_container_width=True):
                    conn.table("corridas").update({"status": "Confirmada", "motorista_nome": st.session_state.user_nome}).eq("id", r['id']).execute()
                    st.rerun()

    # --- VISÃO ADMINISTRADOR ---
    elif perfil == "Administrador":
        st.title("🛡️ Admin")
        ativas = conn.table("corridas").select("*").neq("status", "Finalizada").execute()
        st.table(pd.DataFrame(ativas.data) if ativas.data else [])
        if st.button("Limpar todas as corridas"):
            conn.table("corridas").delete().neq("id", 0).execute()
            st.rerun()
