import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_js_eval import streamlit_js_eval
from geopy.distance import geodesic
import pandas as pd
import urllib.parse

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")
conn = st.connection("supabase", type=SupabaseConnection)

if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.user_nome = ""
    st.session_state.user_tipo = ""

def logout():
    st.session_state.logado = False
    st.rerun()

# --- INTERFACE DE ACESSO ---
if not st.session_state.logado:
    st.title("🛡️ CORRIDA PROTEGIDA")
    aba_log, aba_cad = st.tabs(["Login", "Cadastro"])
    
    with aba_cad:
        tipo = st.radio("Eu sou:", ["Sou Passageiro", "Sou Motorista"], horizontal=True)
        nome = st.text_input("Nome Completo")
        cpf = st.text_input("CPF (números)")
        senha = st.text_input("Senha", type="password")
        if st.button("Finalizar Cadastro"):
            if nome and cpf and senha:
                try:
                    conn.table("usuarios").insert([{"tipo": tipo, "nome": nome, "cpf": cpf, "senha": senha}]).execute()
                    st.success("✅ Cadastro Realizado!")
                except: st.error("Erro no cadastro.")
            else: st.warning("Preencha tudo!")

    with aba_log:
        tipo_l = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="tipo_l")
        l_cpf = st.text_input("CPF", key="l_cpf")
        l_pass = st.text_input("Senha", type="password", key="l_pass")
        if st.button("Entrar"):
            res = conn.table("usuarios").select("nome").eq("cpf", l_cpf).eq("senha", l_pass).eq("tipo", tipo_l).execute()
            if res.data:
                st.session_state.logado = True
                st.session_state.user_nome = res.data[0]['nome']
                st.session_state.user_tipo = tipo_l
                st.rerun()
            else: st.error("Dados incorretos.")

# --- PAINEL LOGADO ---
else:
    st.sidebar.button("Sair", on_click=logout)
    st.title(f"Olá, {st.session_state.user_nome}! 🛡️")

    # CAPTURA DE GPS (Funciona no Celular)
    loc = streamlit_js_eval(data='getCurrentPosition', component_value=None, key='gps_global')

    if st.session_state.user_tipo == "Sou Passageiro":
        st.subheader("📍 Pedir Corrida")
        if loc:
            lat_p = loc['coords']['latitude']
            lon_p = loc['coords']['longitude']
            st.success("Sua localização GPS foi detectada!")
            
            dest = st.text_input("Para onde vamos?")
            if st.button("CHAMAR AGORA 🚀"):
                if dest:
                    conn.table("corridas").insert([{
                        "passageiro": st.session_state.user_nome,
                        "ponto_origem": "Localização via GPS",
                        "lat_origem": lat_p, "lon_origem": lon_p,
                        "ponto_destino": dest, "status": "Aguardando"
                    }]).execute()
                    st.success("Chamada enviada! Aguarde o motorista.")
        else:
            st.warning("Aguardando permissão de GPS do celular...")

    elif st.session_state.user_tipo == "Sou Motorista":
        st.subheader("🛣️ Corridas Próximas")
        res_corridas = conn.table("corridas").select("*").eq("status", "Aguardando").execute()
        
        if not res_corridas.data:
            st.info("Buscando passageiros...")
            if st.button("🔄 Atualizar"): st.rerun()
        else:
            for r in res_corridas.data:
                distancia = 0.0
                tempo = 0
                if loc and r['lat_origem']:
                    # CÁLCULO DE DISTÂNCIA E TEMPO
                    ponto_m = (loc['coords']['latitude'], loc['coords']['longitude'])
                    ponto_p = (r['lat_origem'], r['lon_origem'])
                    distancia = geodesic(ponto_m, ponto_p).km
                    tempo = int(distancia * 4) # Média de 4 min por km
                
                with st.expander(f"📍 Corrida a {distancia:.2f} km de você"):
                    st.write(f"**Destino:** {r['ponto_destino']}")
                    st.write(f"**Tempo Estimado:** {tempo} min para chegar")
                    
                    link_waze = f"https://waze.com{r['lat_origem']},{r['lon_origem']}&navigate=yes"
                    
                    if st.button(f"Aceitar Corrida #{r['id']}"):
                        conn.table("corridas").update({"status": "Em curso"}).eq("id", r['id']).execute()
                        st.success(f"Corrida aceita! O passageiro foi avisado que você chega em {tempo} min.")
                        st.balloons()
                    st.markdown(f'[🚗 Abrir Rota no Waze]({link_waze})')
