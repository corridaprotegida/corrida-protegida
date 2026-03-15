import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_js_eval import streamlit_js_eval
from geopy.distance import geodesic
import pandas as pd
import urllib.parse

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")

# CONEXÃO COM SUPABASE (Puxa dos Secrets do Streamlit)
conn = st.connection("supabase", type=SupabaseConnection)

# --- CONTROLE DE SESSÃO ---
if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.user_nome = ""
    st.session_state.user_tipo = ""

def logout():
    st.session_state.logado = False
    st.rerun()

# --- INTERFACE DE ACESSO (LOGIN/CADASTRO) ---
if not st.session_state.logado:
    st.title("🛡️ CORRIDA PROTEGIDA")
    aba_log, aba_cad = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    
    with aba_cad:
        tipo = st.radio("Seu perfil:", ["Sou Passageiro", "Sou Motorista"], horizontal=True)
        nome = st.text_input("Nome Completo")
        cpf = st.text_input("CPF (números)")
        senha = st.text_input("Senha", type="password")
        if st.button("Finalizar Cadastro"):
            if nome and cpf and senha:
                try:
                    conn.table("usuarios").insert([{"tipo": tipo, "nome": nome, "cpf": cpf, "senha": senha}]).execute()
                    st.success("✅ Cadastro Realizado! Vá para a aba Login.")
                except: st.error("Erro: CPF já cadastrado.")
            else: st.warning("Preencha todos os campos!")

    with aba_log:
        tipo_l = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="tipo_l")
        l_cpf = st.text_input("CPF", key="l_cpf")
        l_pass = st.text_input("Senha", type="password", key="l_pass")
        if st.button("Acessar Painel"):
            res = conn.table("usuarios").select("nome").eq("cpf", l_cpf).eq("senha", l_pass).eq("tipo", tipo_l).execute()
            if res.data:
                st.session_state.logado = True
                st.session_state.user_nome = res.data[0]['nome']
                st.session_state.user_tipo = tipo_l
                st.rerun()
            else: st.error("Dados incorretos.")

# --- PAINEL DO USUÁRIO LOGADO ---
else:
    st.sidebar.button("Sair/Logout", on_click=logout)
    st.title(f"Olá, {st.session_state.user_nome}! 🛡️")

    # CAPTURA DE LOCALIZAÇÃO GPS DO CELULAR
    loc = streamlit_js_eval(data='getCurrentPosition', component_value=None, key='gps_data')

    # --- TELA DO PASSAGEIRO ---
    if st.session_state.user_tipo == "Sou Passageiro":
        st.subheader("📍 Solicitar Nova Corrida")
        
        if loc:
            lat_p = loc['coords']['latitude']
            lon_p = loc['coords']['longitude']
            st.success(f"✅ GPS Ativo: {lat_p:.4f}, {lon_p:.4f}")
            
            destino = st.text_input("🏁 Para onde vamos?")
            if st.button("CHAMAR AGORA 🚀"):
                if destino:
                    conn.table("corridas").insert([{
                        "passageiro": st.session_state.user_nome,
                        "ponto_origem": "GPS em tempo real",
                        "lat_origem": lat_p, "lon_origem": lon_p,
                        "ponto_destino": destino, "status": "Aguardando"
                    }]).execute()
                    st.success("🚀 Chamada enviada! O motorista verá sua posição exata.")
                else: st.warning("Digite o destino primeiro!")
        else:
            st.warning("⚠️ Aguardando GPS... Verifique se a localização está permitida no cadeado do navegador.")
            if st.button("🔄 Tentar Capturar GPS"): st.rerun()

    # --- TELA DO MOTORISTA ---
    elif st.session_state.user_tipo == "Sou Motorista":
        st.subheader("🛣️ Corridas Disponíveis")
        res_corridas = conn.table("corridas").select("*").eq("status", "Aguardando").execute()
        
        if not res_corridas.data:
            st.info("Nenhuma corrida disponível no momento.")
            if st.button("🔄 Atualizar Lista"): st.rerun()
        else:
            for r in res_corridas.data:
                distancia = 0.0
                tempo = 0
                if loc and r['lat_origem']:
                    # Calcula distância e tempo (4 min por km)
                    ponto_m = (loc['coords']['latitude'], loc['coords']['longitude'])
                    ponto_p = (r['lat_origem'], r['lon_origem'])
                    distancia = geodesic(ponto_m, ponto_p).km
                    tempo = int(distancia * 4)
                
                with st.expander(f"📍 Corrida a {distancia:.2f} km de você"):
                    st.write(f"**Passageiro:** {r['passageiro']}")
                    st.write(f"**Destino:** {r['ponto_destino']}")
                    st.write(f"**Previsão:** {tempo} min para buscar")
                    
                    # LINK OFICIAL DO WAZE (Latitude e Longitude)
                    link_waze = f"https://www.waze.com{r['lat_origem']},{r['lon_origem']}&navigate=yes"
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✅ Aceitar #{r['id']}", key=f"ac_{r['id']}"):
                            conn.table("corridas").update({"status": "Em curso"}).eq("id", r['id']).execute()
                            st.success("Corrida Aceita! O passageiro foi avisado.")
                            st.balloons()
                    with col2:
                        # Botão estilizado para abrir o Waze direto
                        st.markdown(f'''<a href="{link_waze}" target="_blank" style="text-decoration: none;">
                                        <div style="background-color: #33ccff; color: white; padding: 10px; border-radius: 8px; text-align: center; font-weight: bold;">
                                            🚗 Abrir no Waze
                                        </div></a>''', unsafe_allow_html=True)

    # --- BOTÃO DE PÂNICO ---
    st.sidebar.markdown("---")
    st.sidebar.error("🚨 CENTRAL DE EMERGÊNCIA")
    msg_sos = urllib.parse.quote(f"SOCORRO! Sou {st.session_state.user_nome} e preciso de ajuda agora!")
    st.sidebar.markdown(f'''<a href="https://wa.me{msg_sos}" target="_blank">
                        <button style="background-color:red; color:white; border:none; padding:15px; width:100%; border-radius:10px; font-weight:bold; cursor:pointer;">
                        🆘 BOTÃO DE PÂNICO</button></a>''', unsafe_allow_html=True)
