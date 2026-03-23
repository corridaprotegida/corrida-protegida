import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_js_eval import get_geolocation
from streamlit_autorefresh import st_autorefresh
from streamlit_folium import st_folium
import folium
import requests
import pandas as pd
import urllib.parse  # <--- ESTA LINHA É ESSENCIAL
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

     # --- 1. VISÃO PASSAGEIRO (CORRIGIDA) ---
    if p_ativo == "Sou Passageiro":
        st.title("Acompanhamento da Viagem 📍")
        
        # Busca corridas que NÃO estão finalizadas para este passageiro
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        
        # VERIFICAÇÃO DE SEGURANÇA: Só prossegue se houver dados na lista
        if res.data and len(res.data) > 0:
            c = res.data[0] # Pega o primeiro item com segurança
            
            st.info(f"Status Atual: **{c['status']}**")
            
            # Tenta localizar coordenadas
            lat_o, lon_o = get_coords_safe(c.get('ponto_origem'))
            lat_d, lon_d = get_coords_safe(c.get('ponto_destino'))
            
            # Só desenha o mapa se as coordenadas forem válidas
            if lat_o and lat_d:
                m = folium.Map(location=[lat_o, lon_o], zoom_start=14)
                folium.Marker([lat_o, lon_o], icon=folium.Icon(color='green', icon='play')).add_to(m)
                folium.Marker([lat_d, lon_d], icon=folium.Icon(color='red', icon='flag')).add_to(m)
                
                # Desenha rota real
                rota = get_route_real(lat_o, lon_o, lat_d, lon_d)
                if rota: 
                    folium.PolyLine(rota, color="#2ecc71", weight=6).add_to(m)
                
                # Mostra o carrinho do motorista se ele já aceitou
                if c.get('lat_motorista'):
                    folium.Marker([c['lat_motorista'], c['lon_motorista']], 
                                  icon=folium.Icon(color='orange', icon='car', prefix='fa')).add_to(m)
                
                # Renderiza o mapa
                st_folium(m, width="100%", height=400, key=f"map_pax_{c['id']}")
            
            if st.button("CANCELAR CORRIDA ❌", key=f"btn_canc_{c['id']}"):
                conn.table("corridas").delete().eq("id", c['id']).execute()
                st.rerun()
        
        else:
            # Se não houver corrida ativa, mostra o formulário de pedido
            st.subheader("Para onde vamos hoje?")
            o = st.text_input("Sua localização atual", key="input_o")
            d = st.text_input("Seu destino", key="input_d")
            v = st.number_input("Quanto deseja oferecer? (R$)", min_value=5.0, value=15.0)
            
            if st.button("SOLICITAR AGORA 🚀"):
                if o and d:
                    conn.table("corridas").insert([{
                        "passageiro": st.session_state.user_nome, 
                        "ponto_origem": o, 
                        "ponto_destino": d, 
                        "valor_total": v, 
                        "status": "Buscando"
                    }]).execute()
                    st.rerun()
                else:
                    st.warning("Preencha a origem e o destino!")

     # --- 2. VISÃO MOTORISTA (CORRIGIDA E BLINDADA) ---
    elif p_ativo == "Sou Motorista":
        st.title("Painel do Motorista 🛣️")
        
        # 1. CAPTURA GPS DO CELULAR (Essencial para o passageiro te ver)
        loc = get_geolocation()
        lat_gps, lon_gps = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (None, None)
        
        if lat_gps:
            # Atualiza sua posição no banco se você estiver em uma corrida ativa
            conn.table("corridas").update({"lat_motorista": lat_gps, "lon_motorista": lon_gps}).eq("motorista_nome", st.session_state.user_nome).eq("status", "Confirmada").execute()
            st.sidebar.success("🛰️ GPS Sincronizado")

        # 2. DIVISÃO DA TELA: MAPA (ESQUERDA) | CHAMADAS (DIREITA)
        col_mapa, col_lista = st.columns([2, 1])

        # Busca chamadas disponíveis ou a corrida que você já aceitou
        res_mot = conn.table("corridas").select("*").or_(f"status.eq.Buscando,and(status.eq.Confirmada,motorista_nome.eq.{st.session_state.user_nome})").execute()
        
        with col_lista:
            st.subheader("🔔 Chamadas")
            if res_mot.data and len(res_mot.data) > 0:
                for r in res_mot.data:
                    with st.container(border=True):
                        st.write(f"👤 **{r['passageiro']}**")
                        st.write(f"💰 R$ {r['valor_total']:.2f}")
                        st.caption(f"🏁 {r['ponto_destino']}")
                        
                        # Se a corrida está apenas buscando, mostra botão de ACEITAR
                        if r['status'] == "Buscando":
                            if st.button(f"ACEITAR #{r['id']}", key=f"mot_acc_{r['id']}", use_container_width=True):
                                conn.table("corridas").update({"status": "Confirmada", "motorista_nome": st.session_state.user_nome}).eq("id", r['id']).execute()
                                st.rerun()
                        
                        # Se já aceitou, mostra o botão de FINALIZAR e o link do WAZE
                        elif r['status'] == "Confirmada":
                            st.success("✅ Corrida em andamento")
                            # Link direto para o APP do Waze
                            addr_waze = urllib.parse.quote(r['ponto_destino'])
                            st.markdown(f'<a href="waze://?q={addr_waze}&navigate=yes"><button style="width:100%; background-color:#33CCFF; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer; margin-bottom:10px;">🚀 ABRIR NO WAZE</button></a>', unsafe_allow_html=True)
                            
                            if st.button("🏁 FINALIZAR CORRIDA", key=f"mot_fin_{r['id']}", type="primary", use_container_width=True):
                                conn.table("corridas").update({"status": "Finalizada"}).eq("id", r['id']).execute()
                                st.balloons()
                                st.rerun()
            else:
                st.info("Aguardando novas chamadas...")

        with col_mapa:
            st.subheader("Mapa de Operação")
            # Centraliza no GPS do motorista ou no centro de PG
            m_lat, m_lon = (lat_gps, lon_gps) if lat_gps else (-25.095, -50.161)
            m_mot = folium.Map(location=[m_lat, m_lon], zoom_start=13)
            
            # Ícone do Motorista (Sempre visível se GPS estiver ON)
            if lat_gps:
                folium.Marker([lat_gps, lon_gps], tooltip="Você", icon=folium.Icon(color='orange', icon='car', prefix='fa')).add_to(m_mot)
            
            # Mostra no mapa os pontos das corridas disponíveis
            if res_mot.data:
                for r in res_mot.data:
                    lat_o, lon_o = get_coords_safe(r['ponto_origem'])
                    if lat_o:
                        cor_icon = 'blue' if r['status'] == "Buscando" else 'green'
                        folium.Marker([lat_o, lon_o], tooltip=f"Passageiro: {r['passageiro']}", icon=folium.Icon(color=cor_icon)).add_to(m_mot)
            
            # Renderiza o mapa com chave única para evitar travamento
            st_folium(m_mot, width="100%", height=500, key="mapa_motorista_tela")


    # --- VISÃO ADMINISTRADOR ---
    elif p_ativo == "Administrador":
        st.title("🛡️ Painel ADM")
        users = conn.table("usuarios").select("*").execute()
        if users.data: st.dataframe(pd.DataFrame(users.data)[['nome', 'tipo', 'logado']], use_container_width=True)
