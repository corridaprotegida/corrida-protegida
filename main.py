import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_js_eval import get_geolocation
from streamlit_autorefresh import st_autorefresh
from streamlit_folium import st_folium
import folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import pandas as pd
import requests
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")
conn = st.connection("supabase", type=SupabaseConnection)
st_autorefresh(interval=5000, key="global_refresh")

# --- FUNÇÕES ---
def get_coords(endereco):
    if not endereco or len(endereco) < 3: return None
    try:
        geolocator = Nominatim(user_agent="corrida_protegida_mobile")
        location = geolocator.geocode(f"{endereco}, Ponta Grossa, PR", timeout=10)
        return (location.latitude, location.longitude) if location else None
    except: return None

def get_route_points(start, end):
    try:
        url = f"http://router.project-osrm.org{start[1]},{start[0]};{end[1]},{end[0]}?overview=full&geometries=geojson"
        r = requests.get(url, timeout=5).json()
        return [(p[1], p[0]) for p in r['routes'][0]['geometry']['coordinates']]
    except: return [start, end]

# --- LOGIN ---
if "user_cpf" not in st.session_state:
    st.session_state.update({"user_cpf": None, "user_nome": None, "user_tipo": None})

if not st.session_state.user_cpf:
    st.title("🛡️ ACESSO RÁPIDO")
    tl = st.radio("Perfil:", ["Sou Passageiro", "Sou Motorista", "Administrador"], horizontal=True)
    lc = st.text_input("CPF")
    ls = st.text_input("Senha", type="password")
    if st.button("ENTRAR AGORA", use_container_width=True):
        res = conn.table("usuarios").select("*").eq("cpf", lc).eq("senha", ls).eq("tipo", tl).execute()
        if res.data:
            u = res.data[0]
            st.session_state.update({"user_cpf": u['cpf'], "user_nome": u['nome'], "user_tipo": u['tipo']})
            st.rerun()
        else: st.error("Dados incorretos.")
else:
    # --- INTERFACE LOGADA ---
    st.sidebar.write(f"👤 {st.session_state.user_nome}")
    if st.sidebar.button("Sair"):
        for k in list(st.session_state.keys()): del st.session_state[k]
        st.rerun()

    # --- VISÃO PASSAGEIRO ---
    if st.session_state.user_tipo == "Sou Passageiro":
        st.subheader("📍 Solicitar Viagem")
        
        # Busca se já tem corrida
        corrida = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        
        if corrida.data:
            c = corrida.data[0]
            st.info(f"Status: {c['status']}")
            if c['motorista_nome']: st.success(f"Motorista: {c['motorista_nome']}")
            
            # Mapa de Acompanhamento
            m_a = folium.Map(location=[-25.09, -50.16], zoom_start=13)
            if c.get('lat_motorista'):
                folium.Marker([c['lat_motorista'], c['lon_motorista']], icon=folium.Icon(color='blue', icon='car', prefix='fa')).add_to(m_a)
            st_folium(m_a, height=300, width=700, key=f"map_track_{c['id']}")
            
            if st.button("CANCELAR CORRIDA ❌", use_container_width=True):
                conn.table("corridas").delete().eq("id", c['id']).execute()
                st.rerun()
        else:
            origem = st.text_input("Sua Localização")
            destino = st.text_input("Para onde vamos?")
            
            if origem and destino:
                co, cd = get_coords(origem), get_coords(destino)
                if co and cd:
                    dist = geodesic(co, cd).km
                    valor = max(7.0, dist * 3.0)
                    st.write(f"📏 {dist:.1f}km | 💰 **R$ {valor:.2f}**")
                    
                    # Rota
                    rota = get_route_points(co, cd)
                    m_p = folium.Map(location=co, zoom_start=14)
                    folium.PolyLine(rota, color="blue", weight=5).add_to(m_p)
                    folium.Marker(co, icon=folium.Icon(color='green')).add_to(m_p)
                    folium.Marker(cd, icon=folium.Icon(color='red')).add_to(m_p)
                    
                    # Key dinâmica para não travar no celular
                    st_folium(m_p, height=300, width=700, key=f"map_pax_{int(time.time())}")
                    
                    if st.button("CONFIRMAR SOLICITAÇÃO 🚀", use_container_width=True):
                        conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": origem, "ponto_destino": destino, "distancia_km": dist, "valor_total": valor, "status": "Buscando"}]).execute()
                        st.rerun()

    # --- VISÃO MOTORISTA ---
    elif st.session_state.user_tipo == "Sou Motorista":
        st.subheader("🛣️ Chamadas Próximas")
        # GPS
        gps = get_geolocation()
        if gps:
            lat, lon = gps['coords']['latitude'], gps['coords']['longitude']
            conn.table("corridas").update({"lat_motorista": lat, "lon_motorista": lon}).eq("motorista_nome", st.session_state.user_nome).eq("status", "Confirmada").execute()

        disponiveis = conn.table("corridas").select("*").eq("status", "Buscando").execute()
        for r in disponiveis.data:
            with st.container(border=True):
                st.write(f"💰 **R$ {r['valor_total']:.2f}** ({r['distancia_km']:.1f}km)")
                st.caption(f"De: {r['ponto_origem']}\nPara: {r['ponto_destino']}")
                if st.button(f"ACEITAR #{r['id']}", key=f"acc_{r['id']}", use_container_width=True):
                    conn.table("corridas").update({"status": "Confirmada", "motorista_nome": st.session_state.user_nome}).eq("id", r['id']).execute()
                    st.rerun()

    # --- VISÃO ADM ---
    elif st.session_state.user_tipo == "Administrador":
        st.title("ADM")
        corridas = conn.table("corridas").select("*").execute()
        st.dataframe(pd.DataFrame(corridas.data) if corridas.data else [])
