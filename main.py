import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_js_eval import get_geolocation
from streamlit_autorefresh import st_autorefresh # Garanta que está no requirements.txt
import pandas as pd
import urllib.parse

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")
conn = st.connection("supabase", type=SupabaseConnection)

# Atualiza a tela automaticamente a cada 5 segundos para ver novas corridas/localização
st_autorefresh(interval=5000, key="datarefresh")

if "user_cpf" not in st.session_state:
    st.session_state.user_cpf = None

# ... (Mantenha sua lógica de Login e Cadastro aqui) ...

# --- PAINEL LOGADO ---
if st.session_state.user_cpf:
    st.sidebar.write(f"👤 **{st.session_state.user_nome}**")
    
    # --- VISÃO MOTORISTA ---
    if st.session_state.user_tipo == "Sou Motorista":
        st.title("Painel do Motorista 🛣️")
        
        # GPS em Tempo Real
        loc = get_geolocation()
        if loc:
            lat_m, lon_m = loc['coords']['latitude'], loc['coords']['longitude']
            conn.table("corridas").update({"lat_motorista": lat_m, "lon_motorista": lon_m}).eq("motorista_nome", st.session_state.user_nome).eq("status", "Confirmada").execute()

        corridas = conn.table("corridas").select("*").eq("status", "Buscando").execute()
        
        for r in corridas.data:
            with st.container(border=True):
                st.subheader(f"Chamada de {r['passageiro']}")
                st.write(f"📍 Destino: {r['ponto_destino']}")
                
                # LINK DIRETO PARA O APP WAZE
                addr = urllib.parse.quote(r['ponto_destino'])
                st.markdown(f'<a href="waze://?q={addr}&navigate=yes"><button style="width:100%; background-color:#00D1FF; border:none; color:white; padding:10px; border-radius:5px; font-weight:bold;">🚀 ABRIR NO APP WAZE</button></a>', unsafe_allow_html=True)
                
                if st.button(f"Aceitar R$ {r['valor_total']}", key=f"acc_{r['id']}"):
                    conn.table("corridas").update({"status": "Confirmada", "motorista_nome": st.session_state.user_nome}).eq("id", r['id']).execute()
                    st.rerun()

    # --- VISÃO PASSAGEIRO ---
    elif st.session_state.user_tipo == "Sou Passageiro":
        st.title("Painel do Passageiro 📍")
        # (Sua lógica de passageiro com o mapa que fizemos antes)
