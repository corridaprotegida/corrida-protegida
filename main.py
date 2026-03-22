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
geolocator = Nominatim(user_agent="corrida_v7_final")

# Atualização automática a cada 10 segundos para não sobrecarregar APIs gratuitas
st_autorefresh(interval=10000, key="global_refresh")

# --- FUNÇÕES DE MAPA E ROTA ---
def get_route_real(lat1, lon1, lat2, lon2):
    """Busca a rota real pelas ruas via OSRM"""
    try:
        url = f"http://router.project-osrm.org{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        r = requests.get(url, timeout=5).json()
        # OSRM retorna [lon, lat], Folium precisa de [lat, lon]
        coords = r['routes'][0]['geometry']['coordinates']
        return [[p[1], p[0]] for p in coords]
    except: return None

def get_coords_safe(endereco):
    """Transforma texto em coordenadas com fallback para Ponta Grossa"""
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
        tl = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista", "Administrador"], horizontal=True, key="login_perfil")
        lc, ls = st.text_input("CPF", key="login_cpf"), st.text_input("Senha", type="password", key="login_senha")
        if st.button("Acessar", key="btn_login"):
            r = conn.table("usuarios").select("*").eq("cpf", lc).eq("senha", ls).eq("tipo", tl).execute()
            if r.data:
                u = r.data[0]
                st.session_state.update({"user_cpf": u['cpf'], "user_nome": u['nome'], "user_tipo": u['tipo']})
                st.rerun()
            else: st.error("Dados incorretos.")

# --- PAINEL LOGADO ---
else:
    perfil_ativo = st.session_state.user_tipo
    if st.session_state.user_tipo == "Administrador":
        perfil_ativo = st.sidebar.radio("Modo Teste:", ["Administrador", "Sou Passageiro", "Sou Motorista"])
    st.sidebar.button("🚪 Sair", on_click=logout, key="btn_logout")

    # --- VISÃO PASSAGEIRO (LINHA VERDE) ---
    if perfil_ativo == "Sou Passageiro":
        st.title("Sua Viagem 📍")
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        
        if res.data:
            c = res.data[0]
            lat_o, lon_o = get_coords_safe(c['ponto_origem'])
            lat_d, lon_d = get_coords_safe(c['ponto_destino'])
            
            # Validação para evitar ValueError
            if lat_o and lat_d:
                m = folium.Map(location=[lat_o, lon_o], zoom_start=14)
                folium.Marker([lat_o, lon_o], tooltip="Início", icon=folium.Icon(color='blue', icon='play')).add_to(m)
                folium.Marker([lat_d, lon_d], tooltip="Fim", icon=folium.Icon(color='red', icon='stop')).add_to(m)
                
                # Rota real seguindo as ruas
                rota = get_route_real(lat_o, lon_o, lat_d, lon_d)
                if rota:
                    folium.PolyLine(rota, color="green", weight=6, opacity=0.8).add_to(m)
                
                # Se tiver motorista, mostra o ícone de carro
                if c.get('lat_motorista'):
                    folium.Marker([c['lat_motorista'], c['lon_motorista']], 
                                  icon=folium.Icon(color='orange', icon='car', prefix='fa')).add_to(m)
                
                st_folium(m, width="100%", height=450, key=f"map_pax_{c['id']}")
            else:
                st.warning("📍 Localizando endereços no mapa... aguarde.")
            
            if st.button("Cancelar Corrida ❌"):
                conn.table("corridas").delete().eq("id", c['id']).execute()
                st.rerun()
        else:
            o = st.text_input("Origem (Ex: Terminal Uvaranas)", key="in_o")
            d = st.text_input("Destino (Ex: Rua Robalo 296)", key="in_d")
            if st.button("SOLICITAR 🚀") and o and d:
                conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": o, "ponto_destino": d, "valor_total": 15.0, "status": "Buscando"}]).execute()
                st.rerun()

    # --- VISÃO MOTORISTA ---
    elif perfil_ativo == "Sou Motorista":
        st.title("Painel do Motorista 🛣️")
        col1, col2 = st.columns([2, 1])
        
        # GPS em tempo real do motorista
        loc = get_geolocation()
        lat_m, lon_m = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (None, None)
        
        with col2:
            st.subheader("Chamadas")
            corridas = conn.table("corridas").select("*").eq("status", "Buscando").execute()
            for r in corridas.data:
                with st.container(border=True):
                    st.write(f"👤 {r['passageiro']}")
                    st.write(f"💰 R$ {r['valor_total']:.2f}")
                    if st.button(f"Aceitar #{r['id']}", key=f"btn_acc_{r['id']}"):
                        conn.table("corridas").update({"status": "Confirmada", "motorista_nome": st.session_state.user_nome, "lat_motorista": lat_m, "lon_motorista": lon_m}).eq("id", r['id']).execute()
                        st.rerun()

        with col1:
            if lat_m:
                m_mot = folium.Map(location=[lat_m, lon_m], zoom_start=13)
                folium.Marker([lat_m, lon_m], icon=folium.Icon(color='orange', icon='car', prefix='fa')).add_to(m_mot)
                
                # Se houver corridas, mostra os pontos de origem no mapa
                for r in corridas.data:
                    lo, no = get_coords_safe(r['ponto_origem'])
                    if lo: folium.Marker([lo, no], popup=f"Passageiro: {r['passageiro']}", icon=folium.Icon(color='blue')).add_to(m_mot)
                
                st_folium(m_mot, width="100%", height=500, key="map_motorista")
            else:
                st.info("🛰️ Ative o GPS do celular para ver o mapa de chamadas.")
