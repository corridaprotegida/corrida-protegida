import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="wide")
conn = st.connection("supabase", type=SupabaseConnection)

# --- 2. INICIALIZAÇÃO SEGURA DO ESTADO (EVITA NAMEERROR) ---
# Isso garante que as variáveis existam antes do app tentar lê-las
if "user_cpf" not in st.session_state:
    st.session_state.user_cpf = None
if "user_nome" not in st.session_state:
    st.session_state.user_nome = None
if "user_tipo" not in st.session_state:
    st.session_state.user_tipo = None

# Função para limpar a sessão ao sair
def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --- 3. LÓGICA DE ACESSO (LOGIN / CADASTRO) ---
if not st.session_state.user_cpf:
    st.title("🛡️ CORRIDA PROTEGIDA")
    st.subheader("Bem-vindo! Identifique-se para continuar.")
    
    tab_login, tab_cadastro = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    
    with tab_cadastro:
        st.write("Crie sua conta em segundos")
        tipo_cad = st.radio("Eu sou:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="reg_tipo")
        nome_cad = st.text_input("Nome Completo", key="reg_nome")
        cpf_cad = st.text_input("CPF (apenas números)", key="reg_cpf")
        senha_cad = st.text_input("Crie uma Senha", type="password", key="reg_senha")
        
        if st.button("Finalizar Cadastro", key="btn_registrar"):
            if nome_cad and cpf_cad and senha_cad:
                # Insere no banco de dados
                conn.table("usuarios").insert([
                    {"tipo": tipo_cad, "nome": nome_cad, "cpf": cpf_cad, "senha": senha_cad}
                ]).execute()
                st.success("✅ Cadastro realizado com sucesso! Agora vá na aba 'Entrar'.")
            else:
                st.warning("⚠️ Por favor, preencha todos os campos.")

    with tab_login:
        st.write("Acesse seu painel")
        tipo_log = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista", "Administrador"], horizontal=True, key="log_tipo")
        cpf_log = st.text_input("CPF", key="log_cpf")
        senha_log = st.text_input("Senha", type="password", key="log_senha")
        
        if st.button("ACESSAR SISTEMA", key="btn_login"):
            # Busca o usuário no Supabase
            query = conn.table("usuarios").select("*").eq("cpf", cpf_log).eq("senha", senha_log).eq("tipo", tipo_log).execute()
            
            # TRATAMENTO DE ERRO DE LISTA (TYPEERROR)
            if query.data and len(query.data) > 0:
                usuario_encontrado = query.data[0] # Pega o primeiro item da lista com segurança
                
                # Salva na sessão do navegador
                st.session_state.user_cpf = usuario_encontrado['cpf']
                st.session_state.user_nome = usuario_encontrado['nome']
                st.session_state.user_tipo = usuario_encontrado['tipo']
                
                st.success(f"Bem-vindo, {st.session_state.user_nome}!")
                st.rerun()
            else:
                st.error("❌ CPF, Senha ou Perfil incorretos.")

# --- 4. ÁREA LOGADA (Onde os próximos módulos entrarão) ---
else:
    st.sidebar.title("🛡️ Menu")
    st.sidebar.write(f"Logado como: **{st.session_state.user_tipo}**")
    st.sidebar.write(f"Usuário: {st.session_state.user_nome}")
    st.sidebar.divider()
    
    if st.sidebar.button("🚪 Sair da Conta"):
        logout()

    # Onde a mágica acontece (Partes 2, 3 e 4)
    st.title(f"Painel de {st.session_state.user_tipo}")
    st.write("Login funcionando 100%! Pronto para a próxima etapa.")
import streamlit as st
from deepface import DeepFace
import cv2
import numpy as np
from PIL import Image

def verificar_identidade():
    st.subheader("🛡️ Verificação de Identidade")
    st.info("Para sua segurança, compare sua foto atual com seu documento (CNH/RG).")

    col1, col2 = st.columns(2)
    
    with col1:
        st.write("1. Foto do Documento")
        foto_doc = st.file_uploader("Upload da CNH/RG", type=['jpg', 'jpeg', 'png'], key="doc_upload")
    
    with col2:
        st.write("2. Reconhecimento Facial")
        foto_selfie = st.camera_input("Tire uma foto agora", key="selfie_cam")

    if foto_doc and foto_selfie:
        if st.button("Validar Identidade"):
            with st.spinner("Analisando biometria facial..."):
                try:
                    # Converte imagens para o formato que o DeepFace aceita (numpy array)
                    img_doc = np.array(Image.open(foto_doc))
                    # O camera_input já retorna um arquivo que abrimos com Image
                    img_selfie = np.array(Image.open(foto_selfie))

                    # Executa a comparação
                    resultado = DeepFace.verify(
                        img1_path = img_doc, 
                        img2_path = img_selfie,
                        model_name = "VGG-Face", # Modelo padrão robusto
                        enforce_detection = True
                    )

                    if resultado["verified"]:
                        st.success(f"✅ Identidade Confirmada! (Similariedade: {resultado['distance']:.2f})")
                        return True
                    else:
                        st.error("❌ As fotos não coincidem. Tente novamente em um local mais iluminado.")
                
                except Exception as e:
                    st.error(f"Erro na detecção: Certifique-se de que seu rosto está visível nas duas fotos.")
    return False

# Exemplo de uso no seu painel:
# if st.session_state.user_tipo == "Sou Motorista":
#    if "verificado" not in st.session_state:
#        st.session_state.verificado = False
#    
#    if not st.session_state.verificado:
#        if verificar_identidade():
#            st.session_state.verificado = True
#            st.rerun()
#    else:
#        st.write("Painel liberado!")
