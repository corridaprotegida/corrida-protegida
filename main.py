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
geolocator = Nominatim(user_agent="corrida_v8_final")

# Atualização automática (Sincroniza motorista/passageiro)
st_autorefresh(interval=8000, key="global_refresh")

# --- FUNÇÕES DE ROTA (OSRM) ---
def get_route_real(lat1, lon1, lat2, lon2):
    """Busca o traçado real das ruas (OSRM)"""
    try:
        url = f"http://router.project-osrm.org{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        r = requests.get(url, timeout=5).json()
        coords = r['routes'][0]['geometry']['coordinates']
        # Inverte para [lat, lon] que o Folium usa
        return [[p[1], p[0]] for p in coords]
    except: return None

def get_coords(endereco):
    """Converte texto em GPS (Filtra para Ponta Grossa)"""
    try:
        if not endereco: return None, None
        loc = geolocator.geocode(endereco + ", Ponta Grossa, PR")
        return (loc.latitude, loc.longitude) if loc else (None, None)
    except: return None, None

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
    p_ativo = st.sidebar.radio("Modo:", ["Sou Passageiro", "Sou Motorista", "Administrador"]) if st.session_state.user_tipo == "Administrador" else st.session_state.user_tipo
    st.sidebar.button("Sair", on_click=logout)

    # --- VISÃO PASSAGEIRO (IGUAL INDRIVE) ---
    if p_ativo == "Sou Passageiro":
        st.title("Sua Corrida 📍")
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        
        if res.data:
            c = res.data[0]
            lat_o, lon_o = get_coords(c['ponto_origem'])
            lat_d, lon_d = get_coords(c['ponto_destino'])
            
            if lat_o and lat_d:
                # Criar Mapa Base
                m = folium.Map(location=[lat_o, lon_o], zoom_start=14, tiles="OpenStreetMap")
                
                # Pontos A e B
                folium.Marker([lat_o, lon_o], tooltip="Início", icon=folium.Icon(color='green', icon='play')).add_to(m)
                folium.Marker([lat_d, lon_d], tooltip="Destino", icon=folium.Icon(color='red', icon='flag')).add_to(m)
                
                # DESENHA A LINHA VERDE (ROTA REAL)
                rota = get_route_real(lat_o, lon_o, lat_d, lon_d)
                if rota:
                    folium.PolyLine(rota, color="#2ecc71", weight=6, opacity=0.8).add_to(m)
                
                # Se tiver motorista, mostra o ícone de carro
                if c.get('lat_motorista'):
                    folium.Marker([c['lat_motorista'], c['lon_motorista']], 
                                  icon=folium.Icon(color='orange', icon='car', prefix='fa')).add_to(m)
                
                st_folium(m, width="100%", height=500, key=f"map_pax_{c['id']}")
            
            if st.button("CANCELAR ❌"):
                conn.table("corridas").delete().eq("id", c['id']).execute()
                st.rerun()
        else:
            o, d = st.text_input("Origem"), st.text_input("Destino")
            v = st.number_input("Sua oferta (R$)", 5.0, value=15.0)
            if st.button("SOLICITAR CORRIDA 🚀") and o and d:
                conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": o, "ponto_destino": d, "valor_total": v, "status": "Buscando"}]).execute()
                st.rerun()

    # --- VISÃO MOTORISTA (MAPA + LISTA) ---
    elif p_ativo == "Sou Motorista":
        st.title("Painel Motorista 🛣️")
        col_map, col_list = st.columns([2, 1]) # Mapa maior na esquerda
        
        loc = get_geolocation()
        lat_m, lon_m = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (None, None)
        
        # Chamadas disponíveis
        corridas = conn.table("corridas").select("*").eq("status", "Buscando").execute()
        
        with col_map:
            if lat_m:
                m_mot = folium.Map(location=[lat_m, lon_m], zoom_start=13)
                folium.Marker([lat_m, lon_m], icon=folium.Icon(color='orange', icon='car', prefix='fa')).add_to(m_mot)
                
                # Mostra rota de cada chamada disponível
                for r in corridas.data:
                    lo, no = get_coords(r['ponto_origem'])
                    ld, nd = get_coords(r['ponto_destino'])
                    if lo and ld:
                        # Rota verde discreta para o motorista ver o trajeto
                        rota_m = get_route_real(lo, no, ld, nd)
                        if rota_m: folium.PolyLine(rota_m, color="green", weight=3, opacity=0.5).add_to(m_mot)
                        folium.Marker([lo, no], icon=folium.Icon(color='blue')).add_to(m_mot)
                
                st_folium(m_mot, width="100%", height=500, key="map_mot")

        with col_list:
            for r in corridas.data:
                with st.container(border=True):
                    st.write(f"👤 {r['passageiro']} | **R$ {r['valor_total']}**")
                    if st.button(f"Aceitar #{r['id']}", use_container_width=True):
                        conn.table("corridas").update({"status": "Confirmada", "motorista_nome": st.session_state.user_nome, "lat_motorista": lat_m, "lon_motorista": lon_m}).eq("id", r['id']).execute()
                        st.rerun()
