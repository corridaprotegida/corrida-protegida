import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_js_eval import get_geolocation
from streamlit_autorefresh import st_autorefresh
from streamlit_folium import st_folium
import folium
import requests
import pandas as pd
from geopy.geocoders import Nominatim

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)
geolocator = Nominatim(user_agent="corrida_v12_gps_sync")

# Atualização rápida (5s) para o GPS parecer fluido
st_autorefresh(interval=5000, key="global_refresh")

# --- FUNÇÕES DE ROTA E GPS ---
def get_route_real(lat1, lon1, lat2, lon2):
    try:
        url = f"http://router.project-osrm.org{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        r = requests.get(url, timeout=5).json()
        if 'routes' in r:
            coords = r['routes'][0]['geometry']['coordinates']
            return [[p[1], p[0]] for p in coords] # Inverte para [lat, lon]
        return None
    except: return None

def get_coords_safe(endereco):
    try:
        if not endereco: return -25.095, -50.161
        loc = geolocator.geocode(endereco + ", Ponta Grossa, PR")
        return (loc.latitude, loc.longitude) if loc else (-25.095, -50.161)
    except: return -25.095, -50.161

# --- ESTADO DE LOGIN ---
if "user_cpf" not in st.session_state:
    st.session_state.update({"user_cpf": None, "user_nome": None, "user_tipo": None})

def logout():
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

# --- LOGIN / CADASTRO ---
if not st.session_state.user_cpf:
    st.title("🛡️ CORRIDA PROTEGIDA")
    t1, t2 = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    with t1:
        tl = st.radio("Perfil:", ["Sou Passageiro", "Sou Motorista", "Administrador"], horizontal=True)
        lc, ls = st.text_input("CPF"), st.text_input("Senha", type="password")
        if st.button("ACESSAR"):
            r = conn.table("usuarios").select("*").eq("cpf", lc).eq("senha", ls).eq("tipo", tl).execute()
            if r.data:
                u = r.data[0]
                st.session_state.update({"user_cpf": u['cpf'], "user_nome": u['nome'], "user_tipo": u['tipo']})
                st.rerun()

# --- PAINEL LOGADO ---
else:
    st.sidebar.write(f"👤 **{st.session_state.user_nome}**")
    p_ativo = st.sidebar.radio("Modo:", ["Administrador", "Sou Passageiro", "Sou Motorista"]) if st.session_state.user_tipo == "Administrador" else st.session_state.user_tipo
    st.sidebar.button("Sair", on_click=logout)

    # --- VISÃO PASSAGEIRO (ACOMPANHAMENTO REAL) ---
    if p_ativo == "Sou Passageiro":
        st.title("Sua Corrida 📍")
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        
        if res.data:
            c = res.data[0]
            lat_o, lon_o = get_coords_safe(c['ponto_origem'])
            lat_d, lon_d = get_coords_safe(c['ponto_destino'])
            
            # Criar Mapa com Rota
            m = folium.Map(location=[lat_o, lon_o], zoom_start=14)
            folium.Marker([lat_o, lon_o], icon=folium.Icon(color='green', icon='play')).add_to(m)
            folium.Marker([lat_d, lon_d], icon=folium.Icon(color='red', icon='flag')).add_to(m)
            
            rota = get_route_real(lat_o, lon_o, lat_d, lon_d)
            if rota: folium.PolyLine(rota, color="#2ecc71", weight=6).add_to(m)
            
            # POSIÇÃO DO MOTORISTA (ATUALIZADA PELO BANCO)
            if c.get('lat_motorista'):
                folium.Marker([c['lat_motorista'], c['lon_motorista']], 
                              popup="Seu Motorista",
                              icon=folium.Icon(color='orange', icon='car', prefix='fa')).add_to(m)
                st.success(f"🚖 {c.get('motorista_nome', 'Motorista')} está a caminho!")
            
            st_folium(m, width="100%", height=500, key=f"map_pax_{c['id']}")
            if st.button("CANCELAR CORRIDA ❌"):
                conn.table("corridas").delete().eq("id", c['id']).execute()
                st.rerun()
        else:
            o, d = st.text_input("Origem"), st.text_input("Destino")
            if st.button("SOLICITAR 🚀") and o and d:
                conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": o, "ponto_destino": d, "valor_total": 15.0, "status": "Buscando"}]).execute()
                st.rerun()

    # --- VISÃO MOTORISTA (ATUALIZA GPS NO BANCO) ---
    elif p_ativo == "Sou Motorista":
        st.title("Painel Motorista 🛣️")
        
        # CAPTURA GPS DO CELULAR
        loc = get_geolocation()
        if loc:
            lat_gps, lon_gps = loc['coords']['latitude'], loc['coords']['longitude']
            # Atualiza o banco para o passageiro ver
            conn.table("corridas").update({"lat_motorista": lat_gps, "lon_motorista": lon_gps}).eq("motorista_nome", st.session_state.user_nome).eq("status", "Confirmada").execute()
            st.sidebar.success("🛰️ GPS Ativo e Sincronizado")

        corridas = conn.table("corridas").select("*").eq("status", "Buscando").execute()
        for r in corridas.data:
            with st.container(border=True):
                st.write(f"👤 {r['passageiro']} | De: {r['ponto_origem']}")
                if st.button(f"ACEITAR CORRIDA #{r['id']}", use_container_width=True):
                    conn.table("corridas").update({"status": "Confirmada", "motorista_nome": st.session_state.user_nome}).eq("id", r['id']).execute()
                    st.rerun()

    # --- VISÃO ADMINISTRADOR ---
    elif p_ativo == "Administrador":
        st.title("🛡️ Painel ADM")
        users = conn.table("usuarios").select("*").execute()
        if users.data: st.dataframe(pd.DataFrame(users.data)[['nome', 'tipo', 'logado']], use_container_width=True)
