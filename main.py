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

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")
conn = st.connection("supabase", type=SupabaseConnection)
st_autorefresh(interval=5000, key="global_refresh")

# --- FUNÇÕES DE MAPA E ROTA ---
def get_coords(endereco):
    if not endereco or len(endereco) < 3: return None
    try:
        geolocator = Nominatim(user_agent="corrida_protegida_pg_final")
        location = geolocator.geocode(f"{endereco}, Ponta Grossa, PR")
        return (location.latitude, location.longitude) if location else None
    except: return None

def get_route_points(start_coords, end_coords):
    """Busca o traçado das ruas via OSRM (Grátis)"""
    try:
        url = f"http://router.project-osrm.org{start_coords[1]},{start_coords[0]};{end_coords[1]},{end_coords[0]}?overview=full&geometries=geojson"
        r = requests.get(url).json()
        coords = r['routes'][0]['geometry']['coordinates']
        return [(p[1], p[0]) for p in coords] 
    except:
        return [start_coords, end_coords]

def criar_mapa_estilo_google(centro, zoom=14):
    """Cria um mapa com as imagens (tiles) do Google Maps"""
    return folium.Map(
        location=centro,
        zoom_start=zoom,
        tiles='https://mt1.google.com{x}&y={y}&z={z}',
        attr='Google Maps'
    )

def logout():
    if st.session_state.get("user_cpf"):
        try: conn.table("usuarios").update({"logado": False}).eq("cpf", st.session_state.user_cpf).execute()
        except: pass
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

# --- ESTADO DA SESSÃO ---
if "user_cpf" not in st.session_state:
    st.session_state.update({"user_cpf": None, "user_nome": None, "user_tipo": None})

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
            st.success("✅ Conta criada!")

    with t1:
        tl = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista", "Administrador"], horizontal=True)
        lc, ls = st.text_input("CPF", key="l_c"), st.text_input("Senha", type="password", key="l_s")
        if st.button("Acessar Sistema"):
            res = conn.table("usuarios").select("*").eq("cpf", lc).eq("senha", ls).eq("tipo", tl).execute()
            if res.data and len(res.data) > 0:
                u = res.data[0]
                st.session_state.update({"user_cpf": u['cpf'], "user_nome": u['nome'], "user_tipo": u['tipo']})
                conn.table("usuarios").update({"logado": True}).eq("cpf", u['cpf']).execute()
                st.rerun()
            else: st.error("❌ Dados incorretos ou perfil errado.")

# --- PAINEL LOGADO ---
else:
    st.sidebar.write(f"👤 **{st.session_state.user_nome}**")
    if st.sidebar.button("🚪 Sair"): logout()
    
    # --- VISÃO PASSAGEIRO ---
    if st.session_state.user_tipo == "Sou Passageiro":
        st.title("Pedir Corrida 📍")
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        
        if res.data:
            c = res.data[0]
            st.warning(f"Status: {c['status']}")
            m_track = criar_mapa_estilo_google([-25.0916, -50.1668], 13)
            if c.get('lat_motorista'):
                folium.Marker([c['lat_motorista'], c['lon_motorista']], icon=folium.Icon(color='blue', icon='car', prefix='fa')).add_to(m_track)
            st_folium(m_track, height=300, width=700, key="map_track")
            if st.button("Cancelar"):
                conn.table("corridas").delete().eq("id", c['id']).execute()
                st.rerun()
        else:
            o_txt = st.text_input("Origem (Ex: Terminal Uvaranas)")
            d_txt = st.text_input("Destino (Ex: Rua Robalo 296)")
            if o_txt and d_txt:
                c_o, c_d = get_coords(o_txt), get_coords(d_txt)
                if c_o and c_d:
                    dist = geodesic(c_o, c_d).km
                    valor = max(6.0, dist * 2.8)
                    st.info(f"📏 {dist:.2f} km | 💰 R$ {valor:.2f}")
                    
                    # MAPA ESTILO GOOGLE COM ROTA NAS RUAS
                    rota = get_route_points(c_o, c_d)
                    m = criar_mapa_estilo_google(c_o, 14)
                    folium.Marker(c_o, icon=folium.Icon(color='green', icon='play')).add_to(m)
                    folium.Marker(c_d, icon=folium.Icon(color='red', icon='stop')).add_to(m)
                    folium.PolyLine(rota, color="#4285F4", weight=6, opacity=0.8).add_to(m) # Azul Google
                    st_folium(m, height=400, width=700, key="map_req")

                    if st.button("CHAMAR AGORA 🚀", use_container_width=True):
                        conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": o_txt, "ponto_destino": d_txt, "distancia_km": dist, "valor_total": valor, "status": "Buscando"}]).execute()
                        st.rerun()

    # --- VISÃO MOTORISTA ---
    elif st.session_state.user_tipo == "Sou Motorista":
        st.title("Painel Motorista 🛣️")
        loc = get_geolocation()
        if loc:
            lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
            conn.table("corridas").update({"lat_motorista": lat, "lon_motorista": lon}).eq("motorista_nome", st.session_state.user_nome).eq("status", "Confirmada").execute()

        disponiveis = conn.table("corridas").select("*").eq("status", "Buscando").execute()
        for r in disponiveis.data:
            with st.container(border=True):
                st.write(f"📍 {r['ponto_origem']} ➡️ {r['ponto_destino']}")
                st.write(f"💰 **R$ {r['valor_total']:.2f}**")
                if st.button(f"Aceitar #{r['id']}", use_container_width=True):
                    conn.table("corridas").update({"status": "Confirmada", "motorista_nome": st.session_state.user_nome}).eq("id", r['id']).execute()
                    st.rerun()

    # --- VISÃO ADMINISTRADOR ---
    elif st.session_state.user_tipo == "Administrador":
        st.title("🛡️ Admin")
        corridas = conn.table("corridas").select("*").execute()
        st.dataframe(pd.DataFrame(corridas.data) if corridas.data else [])
        if st.button("Limpar Tudo"):
            conn.table("corridas").delete().neq("id", 0).execute()
            st.rerun()
