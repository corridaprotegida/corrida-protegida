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

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)
geolocator = Nominatim(user_agent="corrida_v9_final")

# Atualização automática a cada 10 segundos
st_autorefresh(interval=10000, key="global_refresh")

# --- FUNÇÃO DE ROTA E TEMPO (OSRM) ---
def get_route_info(lat1, lon1, lat2, lon2):
    """Retorna geometria da rota, tempo (min) e distância (km)"""
    try:
        url = f"http://router.project-osrm.org{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
        r = requests.get(url, timeout=5).json()
        route = r['routes'][0]
        coords = route['geometry']['coordinates']
        distancia = route['distance'] / 1000 # km
        tempo = route['duration'] / 60 # min
        
        # Converte coordenadas para [lat, lon]
        path = [[p[1], p[0]] for p in coords]
        return path, f"{distancia:.1f} km", f"{int(tempo)} min"
    except: return None, None, None

def get_coords(endereco):
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
            if r.data and len(r.data) > 0:
                u = r.data[0]
                st.session_state.update({"user_cpf": u['cpf'], "user_nome": u['nome'], "user_tipo": u['tipo']})
                st.rerun()

# --- PAINEL LOGADO ---
else:
    st.sidebar.write(f"👤 **{st.session_state.user_nome}**")
    p_ativo = st.sidebar.radio("Modo:", ["Sou Passageiro", "Sou Motorista", "Administrador"]) if st.session_state.user_tipo == "Administrador" else st.session_state.user_tipo
    st.sidebar.button("Sair", on_click=logout)

    # --- VISÃO PASSAGEIRO (ESTILO INDRIVE/UBER) ---
    if p_ativo == "Sou Passageiro":
        st.title("Acompanhamento da Viagem 📍")
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        
        if res.data and len(res.data) > 0:
            c = res.data[0]
            lat_o, lon_o = get_coords(c['ponto_origem'])
            lat_d, lon_d = get_coords(c['ponto_destino'])
            
            if lat_o and lat_d:
                # Busca rota e tempo
                path, dist_txt, tempo_txt = get_route_info(lat_o, lon_o, lat_d, lon_d)
                
                # Exibe métricas de tempo e distância
                col_m1, col_m2, col_m3 = st.columns(3)
                col_m1.metric("Status", c['status'])
                col_m2.metric("Distância", dist_txt)
                col_m3.metric("Tempo Est.", tempo_txt)

                # Mapa com linha verde
                m = folium.Map(location=[lat_o, lon_o], zoom_start=14)
                folium.Marker([lat_o, lon_o], icon=folium.Icon(color='green', icon='play')).add_to(m)
                folium.Marker([lat_d, lon_d], icon=folium.Icon(color='red', icon='flag')).add_to(m)
                
                if path:
                    folium.PolyLine(path, color="#2ecc71", weight=6, opacity=0.8).add_to(m)
                
                # Ícone do Motorista
                if c.get('lat_motorista'):
                    folium.Marker([c['lat_motorista'], c['lon_motorista']], 
                                  icon=folium.Icon(color='orange', icon='car', prefix='fa')).add_to(m)
                
                st_folium(m, width="100%", height=500, key=f"map_pax_{c['id']}")
            
            if st.button("CANCELAR ❌"):
                conn.table("corridas").delete().eq("id", c['id']).execute()
                st.rerun()
        else:
            o, d = st.text_input("Origem"), st.text_input("Destino")
            v = st.number_input("Oferta (R$)", 5.0, value=15.0)
            if st.button("SOLICITAR CORRIDA 🚀") and o and d:
                conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": o, "ponto_destino": d, "valor_total": v, "status": "Buscando"}]).execute()
                st.rerun()

    # --- VISÃO MOTORISTA ---
    elif p_ativo == "Sou Motorista":
        st.title("Central do Motorista 🛣️")
        col_m, col_l = st.columns([2, 1])
        
        loc = get_geolocation()
        lat_m, lon_m = (loc['coords']['latitude'], loc['coords']['longitude']) if loc else (None, None)
        
        corridas = conn.table("corridas").select("*").eq("status", "Buscando").execute()
        
        with col_m:
            if lat_m:
                m_mot = folium.Map(location=[lat_m, lon_m], zoom_start=13)
                folium.Marker([lat_m, lon_m], icon=folium.Icon(color='orange', icon='car', prefix='fa')).add_to(m_mot)
                
                for r in corridas.data:
                    lo, no = get_coords(r['ponto_origem'])
                    if lo:
                        folium.Marker([lo, no], popup=f"Cliente: {r['passageiro']}", icon=folium.Icon(color='blue')).add_to(m_mot)
                st_folium(m_mot, width="100%", height=500, key="map_motorista")

        with col_l:
            st.subheader("Chamadas")
            for r in corridas.data:
                with st.container(border=True):
                    st.write(f"👤 {r['passageiro']}")
                    st.write(f"💰 R$ {r['valor_total']:.2f}")
                    
                    addr = urllib.parse.quote(r['ponto_destino'])
                    st.markdown(f'<a href="waze://?q={addr}&navigate=yes"><button style="width:100%; background-color:#33CCFF; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer;">ABRIR NO WAZE</button></a>', unsafe_allow_html=True)
                    
                    if st.button(f"ACEITAR #{r['id']}", key=f"ac_{r['id']}"):
                        conn.table("corridas").update({"status": "Confirmada", "motorista_nome": st.session_state.user_nome, "lat_motorista": lat_m, "lon_motorista": lon_m}).eq("id", r['id']).execute()
                        st.rerun()
    # --- 3. VISÃO ADMINISTRADOR (CORRIGIDA) ---
    elif p_ativo == "Administrador":
        st.title("🛡️ Painel de Controle ADM")
        
        # Criamos as abas para organizar
        t_u, t_c, t_f = st.tabs(["👥 Usuários", "🚖 Corridas Ativas", "📊 Financeiro"])

        with t_u:
            st.subheader("Gerenciar Usuários")
            try:
                users = conn.table("usuarios").select("*").execute()
                if users.data and len(users.data) > 0:
                    df_u = pd.DataFrame(users.data)
                    # Filtra apenas colunas que existem para evitar KeyError
                    cols = [c for c in ['nome', 'tipo', 'cpf', 'logado'] if c in df_u.columns]
                    st.dataframe(df_u[cols], use_container_width=True)
                    
                    u_del = st.selectbox("Remover Usuário:", df_u['nome'], key="adm_del_user")
                    if st.button("Remover Permanentemente", type="primary"):
                        conn.table("usuarios").delete().eq("nome", u_del).execute()
                        st.success(f"Usuário {u_del} removido!")
                        st.rerun()
                else:
                    st.info("Nenhum usuário cadastrado no banco.")
            except Exception as e:
                st.error(f"Erro ao carregar usuários: {e}")

        with t_c:
            st.subheader("Monitoramento em Tempo Real")
            try:
                cor_ativas = conn.table("corridas").select("*").neq("status", "Finalizada").execute()
                if cor_ativas.data and len(cor_ativas.data) > 0:
                    for ca in cor_ativas.data:
                        with st.container(border=True):
                            st.write(f"🆔 **ID:** {ca['id']} | **Status:** {ca['status']}")
                            st.write(f"👤 {ca['passageiro']} ➡️ {ca['motorista_nome'] or 'Buscando...'}")
                            st.write(f"💰 Valor: R$ {ca['valor_total']:.2f}")
                            if st.button(f"Forçar Encerramento #{ca['id']}", key=f"adm_force_{ca['id']}"):
                                conn.table("corridas").update({"status": "Finalizada"}).eq("id", ca['id']).execute()
                                st.rerun()
                else:
                    st.info("Nenhuma corrida ativa no momento.")
            except Exception as e:
                st.error(f"Erro ao carregar corridas: {e}")

        with t_f:
            st.subheader("Resumo de Ganhos")
            try:
                fina = conn.table("corridas").select("valor_total").eq("status", "Finalizada").execute()
                if fina.data:
                    total = sum(i['valor_total'] for i in fina.data)
                    st.metric("Volume Total Finalizado", f"R$ {total:.2f}")
                else:
                    st.metric("Volume Total Finalizado", "R$ 0,00")
            except:
                st.write("Dados financeiros indisponíveis.")
