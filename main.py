import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_js_eval import get_geolocation
from streamlit_autorefresh import st_autorefresh
from streamlit_folium import st_folium
import folium
import requests
import pandas as pd
import urllib.parse
from geopy.geocoders import Nominatim

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)
geolocator = Nominatim(user_agent="corrida_v6")
st_autorefresh(interval=8000, key="global_refresh")

# --- FUNÇÃO PARA PEGAR ROTA REAL (OSRM) ---
def get_route(lat1, lon1, lat2, lon2):
    try:
        url = f"http://router.project-osrm.org{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        r = requests.get(url).json()
        return r['routes'][0]['geometry']['coordinates']
    except: return None

def get_coords(endereco):
    try:
        loc = geolocator.geocode(endereco + ", Ponta Grossa, PR")
        return (loc.latitude, loc.longitude) if loc else (None, None)
    except: return (None, None)

# --- ESTADO E LOGOUT ---
if "user_cpf" not in st.session_state:
    st.session_state.update({"user_cpf": None, "user_nome": None, "user_tipo": None})

def logout():
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

# --- LOGIN / CADASTRO (Simplificado para o exemplo) ---
if not st.session_state.user_cpf:
    st.title("🛡️ CORRIDA PROTEGIDA")
    t1, t2 = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    with t1:
        tl = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista", "Administrador"], horizontal=True)
        lc, ls = st.text_input("CPF"), st.text_input("Senha", type="password")
        if st.button("Acessar"):
            r = conn.table("usuarios").select("*").eq("cpf", lc).eq("senha", ls).eq("tipo", tl).execute()
            if r.data:
                u = r.data[0]
                st.session_state.update({"user_cpf": u['cpf'], "user_nome": u['nome'], "user_tipo": u['tipo']})
                st.rerun()

# --- PAINEL LOGADO ---
else:
    perfil_ativo = st.session_state.user_tipo
    if st.session_state.user_tipo == "Administrador":
        perfil_ativo = st.sidebar.radio("Modo Teste:", ["Administrador", "Sou Passageiro", "Sou Motorista"])
    st.sidebar.button("🚪 Sair", on_click=logout)

    # --- VISÃO PASSAGEIRO (COM LINHA VERDE) ---
    if perfil_ativo == "Sou Passageiro":
        st.title("Sua Viagem 📍")
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        
        if res.data:
            c = res.data[0]
            lat_o, lon_o = get_coords(c['ponto_origem'])
            lat_d, lon_d = get_coords(c['ponto_destino'])
            
            # Criar Mapa Folium
            m = folium.Map(location=[lat_o, lon_o], zoom_start=14)
            folium.Marker([lat_o, lon_o], tooltip="Origem", icon=folium.Icon(color='blue')).add_to(m)
            folium.Marker([lat_d, lon_d], tooltip="Destino", icon=folium.Icon(color='red')).add_to(m)
            
            # Desenhar Rota Real
            route_coords = get_route(lat_o, lon_o, lat_d, lon_d)
            if route_coords:
                # Folium usa [lat, lon], OSRM retorna [lon, lat]
                path = [[p[1], p[0]] for p in route_coords]
                folium.PolyLine(path, color="green", weight=5, opacity=0.8).add_to(m)
            
            st_folium(m, width=700, height=400)
            if st.button("Cancelar"):
                conn.table("corridas").delete().eq("id", c['id']).execute()
                st.rerun()
        else:
            o, d = st.text_input("Origem"), st.text_input("Destino")
            if st.button("SOLICITAR 🚀") and o and d:
                conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": o, "ponto_destino": d, "valor_total": 15.0, "status": "Buscando"}]).execute()
                st.rerun()

    # --- VISÃO MOTORISTA (TELA DIVIDIDA) ---
    elif perfil_ativo == "Sou Motorista":
        st.title("Painel do Motorista 🛣️")
        col1, col2 = st.columns([2, 1])
        
        corridas = conn.table("corridas").select("*").eq("status", "Buscando").execute()
        
        with col1:
            st.subheader("Mapa de Rotas")
            if corridas.data:
                c = corridas.data[0] # Mostra a primeira da lista no mapa
                lo, no = get_coords(c['ponto_origem'])
                ld, nd = get_coords(c['ponto_destino'])
                m_mot = folium.Map(location=[lo, no], zoom_start=13)
                path_mot = get_route(lo, no, ld, nd)
                if path_mot:
                    folium.PolyLine([[p[1], p[0]] for p in path_mot], color="blue", weight=4).add_to(m_mot)
                st_folium(m_mot, width=600, height=400, key="map_mot")

        with col2:
            st.subheader("Chamadas")
            for r in corridas.data:
                st.write(f"👤 {r['passageiro']}")
                st.write(f"🏁 {r['ponto_destino']}")
                if st.button(f"ACEITAR #{r['id']}"):
                    conn.table("corridas").update({"status": "Confirmada", "motorista_nome": st.session_state.user_nome}).eq("id", r['id']).execute()
                    st.rerun()
