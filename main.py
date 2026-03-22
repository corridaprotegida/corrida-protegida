import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_js_eval import get_geolocation
from streamlit_autorefresh import st_autorefresh
from streamlit_folium import st_folium
import folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import pandas as pd

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")

# Conexão Supabase
conn = st.connection("supabase", type=SupabaseConnection)

# Atualização automática a cada 5 segundos
st_autorefresh(interval=5000, key="global_refresh")

# --- FUNÇÕES AUXILIARES ---
def get_coords(endereco):
    """Converte texto em coordenadas (Lat, Lon) focando em Ponta Grossa"""
    if not endereco or len(endereco) < 3: return None
    try:
        geolocator = Nominatim(user_agent="corrida_protegida_test_pg")
        location = geolocator.geocode(f"{endereco}, Ponta Grossa, PR")
        return (location.latitude, location.longitude) if location else None
    except:
        return None

def logout():
    if st.session_state.get("user_cpf"):
        try:
            conn.table("usuarios").update({"logado": False}).eq("cpf", st.session_state.user_cpf).execute()
        except: pass
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --- INICIALIZAÇÃO DO ESTADO ---
if "user_cpf" not in st.session_state:
    st.session_state.update({"user_cpf": None, "user_nome": None, "user_tipo": None})

# --- INTERFACE DE ACESSO (LOGIN/CADASTRO) ---
if not st.session_state.user_cpf:
    st.title("🛡️ CORRIDA PROTEGIDA")
    t1, t2 = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    
    with t2:
        tp = st.radio("Eu sou:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="reg_tp")
        n = st.text_input("Nome Completo")
        c = st.text_input("CPF (apenas números)")
        s = st.text_input("Senha", type="password")
        pix = st.text_input("Chave PIX") if tp == "Sou Motorista" else ""
        if st.button("Finalizar Cadastro"):
            if n and c and s:
                conn.table("usuarios").insert([{"tipo": tp, "nome": n, "cpf": c, "senha": s, "chave_pix": pix}]).execute()
                st.success("✅ Cadastro realizado! Vá em 'Entrar'.")
            else: st.warning("Preencha todos os campos!")

    with t1:
        tl = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista", "Administrador"], horizontal=True)
        lc = st.text_input("CPF", key="login_cpf")
        ls = st.text_input("Senha", type="password", key="login_pw")
        
        if st.button("Acessar Sistema"):
            # BUSCA NO SUPABASE
            res = conn.table("usuarios").select("*").eq("cpf", lc).eq("senha", ls).eq("tipo", tl).execute()
            
            if res.data and len(res.data) > 0:
                user = res.data[0] # Pega o primeiro item da lista retornada
                st.session_state.user_cpf = user['cpf']
                st.session_state.user_nome = user['nome']
                st.session_state.user_tipo = user['tipo']
                conn.table("usuarios").update({"logado": True}).eq("cpf", user['cpf']).execute()
                st.rerun()
            else:
                st.error("❌ Dados incorretos ou usuário não cadastrado neste perfil.")

# --- PAINEL LOGADO ---
else:
    st.sidebar.subheader(f"👤 {st.session_state.user_nome}")
    st.sidebar.caption(f"Perfil: {st.session_state.user_tipo}")
    if st.sidebar.button("🚪 Sair"): logout()
    
    perfil = st.session_state.user_tipo

    # --- VISÃO PASSAGEIRO ---
    if perfil == "Sou Passageiro":
        st.title("Solicitar Corrida 📍")
        
        # Verifica se há corrida ativa
        corrida_ativa = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        
        if corrida_ativa.data:
            c = corrida_ativa.data[0]
            st.info(f"Sua corrida está: **{c['status']}**")
            if c['motorista_nome']: st.success(f"Motorista a caminho: {c['motorista_nome']}")
            
            # Mapa de Acompanhamento
            m_pax = folium.Map(location=[-25.0916, -50.1668], zoom_start=13)
            if c['lat_motorista'] and c['lon_motorista']:
                folium.Marker([c['lat_motorista'], c['lon_motorista']], 
                              icon=folium.Icon(color='blue', icon='car', prefix='fa'),
                              popup="Motorista").add_to(m_pax)
            st_folium(m_pax, height=300, width=700, key="map_track")
            
            if st.button("Cancelar Corrida ❌"):
                conn.table("corridas").delete().eq("id", c['id']).execute()
                st.rerun()
        else:
            origem = st.text_input("Origem", placeholder="Ex: Terminal Uvaranas")
            destino = st.text_input("Destino", placeholder="Ex: Rua Robalo 296")
            
            if origem and destino:
                c_o = get_coords(origem)
                c_d = get_coords(destino)
                
                if c_o and c_d:
                    dist = geodesic(c_o, c_d).km
                    valor = max(6.0, dist * 2.8) # R$ 2,80/km, min R$ 6,00
                    
                    st.write(f"📏 Distância: **{dist:.2f} km** | 💰 Valor: **R$ {valor:.2f}**")
                    
                    # Mapa de Prévia
                    m_previa = folium.Map(location=c_o, zoom_start=14)
                    folium.Marker(c_o, color='green', popup="Origem").add_to(m_previa)
                    folium.Marker(c_d, color='red', popup="Destino").add_to(m_previa)
                    folium.PolyLine([c_o, c_d], color="blue", weight=3).add_to(m_previa)
                    st_folium(m_previa, height=300, width=700, key="map_previa")

                    if st.button("CHAMAR AGORA 🚀", use_container_width=True):
                        conn.table("corridas").insert([{
                            "passageiro": st.session_state.user_nome,
                            "ponto_origem": origem, "ponto_destino": destino,
                            "distancia_km": dist, "valor_total": valor, "status": "Buscando"
                        }]).execute()
                        st.rerun()
                else:
                    st.caption("Aguardando endereços válidos...")

    # --- VISÃO MOTORISTA ---
    elif perfil == "Sou Motorista":
        st.title("Chamadas Próximas 🛣️")
        
        # GPS em tempo real (Envia para o banco se estiver em corrida)
        loc = get_geolocation()
        if loc:
            lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
            conn.table("corridas").update({"lat_motorista": lat, "lon_motorista": lon}).eq("motorista_nome", st.session_state.user_nome).eq("status", "Confirmada").execute()

        # Listar corridas pendentes
        disponiveis = conn.table("corridas").select("*").eq("status", "Buscando").execute()
        
        if not disponiveis.data:
            st.write("☕ Nenhuma chamada no momento. Aguarde...")
        
        for r in disponiveis.data:
            with st.container(border=True):
                st.write(f"👤 {r['passageiro']} | **R$ {r['valor_total']:.2f}**")
                st.caption(f"De: {r['ponto_origem']}\nPara: {r['ponto_destino']}")
                if st.button(f"Aceitar Chamada #{r['id']}", key=f"btn_{r['id']}", use_container_width=True):
                    conn.table("corridas").update({"status": "Confirmada", "motorista_nome": st.session_state.user_nome}).eq("id", r['id']).execute()
                    st.rerun()

    # --- VISÃO ADM ---
    elif perfil == "Administrador":
        st.title("🛡️ Gestão Central")
        corridas = conn.table("corridas").select("*").execute()
        if corridas.data:
            df = pd.DataFrame(corridas.data)
            st.dataframe(df)
            if st.button("Limpar Histórico"):
                conn.table("corridas").delete().neq("id", 0).execute()
                st.rerun()
