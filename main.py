import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_js_eval import get_geolocation
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import urllib.parse
import base64

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")
conn = st.connection("supabase", type=SupabaseConnection)

# Atualização automática a cada 5 segundos para sincronizar as telas
st_autorefresh(interval=5000, key="global_refresh")

# --- FUNÇÃO DE NOTIFICAÇÃO SONORA ---
def play_notification_sound():
    # Som de "ping" curto e profissional (base64 para não precisar de arquivo externo)
    audio_html = """
        <audio autoplay>
            <source src="https://codeskulptor-demos.commondatastorage.googleapis.com" type="audio/mp3">
        </audio>
    """
    st.markdown(audio_html, unsafe_allow_html=True)

# --- INICIALIZAÇÃO DO ESTADO ---
if "user_cpf" not in st.session_state:
    st.session_state.user_cpf = None
if "user_nome" not in st.session_state:
    st.session_state.user_nome = None
if "user_tipo" not in st.session_state:
    st.session_state.user_tipo = None
if "last_order_count" not in st.session_state:
    st.session_state.last_order_count = 0

def logout():
    if st.session_state.user_cpf:
        try:
            conn.table("usuarios").update({"logado": False}).eq("cpf", st.session_state.user_cpf).execute()
        except: pass
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --- TELA DE ACESSO ---
if not st.session_state.user_cpf:
    st.title("🛡️ CORRIDA PROTEGIDA")
    t1, t2 = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    
    with t2:
        st.subheader("Criar Nova Conta")
        tp = st.radio("Eu sou:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="reg_p")
        n = st.text_input("Nome Completo", key="reg_n")
        c = st.text_input("CPF (números)", key="reg_c")
        pix = st.text_input("Chave PIX", key="reg_pix") if tp == "Sou Motorista" else ""
        s = st.text_input("Senha", type="password", key="reg_s")
        if st.button("Finalizar Cadastro", key="reg_btn"):
            if n and c and s:
                conn.table("usuarios").insert([{"tipo": tp, "nome": n, "cpf": c, "senha": s, "chave_pix": pix}]).execute()
                st.success("✅ Cadastrado!")
            else: st.warning("Preencha tudo!")

    with t1:
        st.subheader("Acessar Painel")
        tl = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista", "Administrador"], horizontal=True, key="log_tp")
        lc = st.text_input("CPF", key="log_c")
        ls = st.text_input("Senha", type="password", key="log_s")
        if st.button("Acessar", key="log_btn"):
            r = conn.table("usuarios").select("*").eq("cpf", lc).eq("senha", ls).eq("tipo", tl).execute()
            if r.data:
                u = r.data[0]
                st.session_state.user_cpf, st.session_state.user_nome, st.session_state.user_tipo = u['cpf'], u['nome'], u['tipo']
                conn.table("usuarios").update({"logado": True}).eq("cpf", u['cpf']).execute()
                st.rerun()
            else: st.error("Dados incorretos.")

# --- PAINEL LOGADO ---
else:
    st.sidebar.write(f"👤 **{st.session_state.user_nome}**")
    
    perfil_ativo = st.session_state.user_tipo
    if st.session_state.user_tipo == "Administrador":
        st.sidebar.divider()
        st.sidebar.subheader("🛠️ Modo de Teste")
        perfil_ativo = st.sidebar.radio("Ver como:", ["Administrador", "Sou Passageiro", "Sou Motorista"])
    
    st.sidebar.button("🚪 Sair", on_click=logout, key="btn_out")

    # --- VISÃO PASSAGEIRO ---
    if perfil_ativo == "Sou Passageiro":
        st.title("Painel do Passageiro 📍")
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        
        if res.data:
            c = res.data[0]
            st.info(f"Status: **{c['status']}**")
            if c['status'] == "Confirmada" and c.get('lat_motorista'):
                df_mapa = pd.DataFrame({'lat': [c['lat_motorista']], 'lon': [c['lon_motorista']]})
                st.map(df_mapa)
            if st.button("Cancelar ❌", key=f"pax_del_{c['id']}"):
                conn.table("corridas").delete().eq("id", c['id']).execute()
                st.rerun()
        else:
            o, d = st.text_input("Origem"), st.text_input("Destino")
            v = st.number_input("Sua oferta (R$)", 5.0, value=15.0)
            if st.button("SOLICITAR 🚀"):
                conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": o, "ponto_destino": d, "valor_total": v, "status": "Buscando"}]).execute()
                st.rerun()

    # --- VISÃO MOTORISTA ---
    elif perfil_ativo == "Sou Motorista":
        st.title("Painel do Motorista 🛣️")
        
        # Atualiza Localização
        loc = get_geolocation()
        if loc:
            lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
            conn.table("corridas").update({"lat_motorista": lat, "lon_motorista": lon}).eq("motorista_nome", st.session_state.user_nome).eq("status", "Confirmada").execute()

        # Busca Chamadas e Toca Som se houver novidade
        corridas = conn.table("corridas").select("*").eq("status", "Buscando").execute()
        
        if len(corridas.data) > st.session_state.last_order_count:
            play_notification_sound()
            st.toast("🔔 Nova chamada disponível!")
        st.session_state.last_order_count = len(corridas.data)

        st.subheader("Chamadas Disponíveis")
        for r in corridas.data:
            with st.container(border=True):
                st.write(f"👤 {r['passageiro']} | R$ {r['valor_total']:.2f}")
                addr = urllib.parse.quote(r['ponto_destino'])
                st.markdown(f'<a href="waze://?q={addr}&navigate=yes"><button style="width:100%; background-color:#33CCFF; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold;">🚀 APP WAZE</button></a>', unsafe_allow_html=True)
                if st.button(f"Aceitar #{r['id']}", key=f"acc_{r['id']}", use_container_width=True):
                    conn.table("corridas").update({"status": "Confirmada", "motorista_nome": st.session_state.user_nome}).eq("id", r['id']).execute()
                    st.rerun()

    # --- VISÃO ADMINISTRADOR ---
    elif perfil_ativo == "Administrador":
        st.title("🛡️ Painel ADM")
        t_u, t_c, t_f = st.tabs(["👥 Usuários", "🚖 Corridas", "📊 Financeiro"])
        
        with t_u:
            users = conn.table("usuarios").select("*").execute()
            if users.data:
                df = pd.DataFrame(users.data)
                st.dataframe(df[['nome', 'tipo', 'cpf', 'logado']], use_container_width=True)
        
        with t_c:
            ativas = conn.table("corridas").select("*").neq("status", "Finalizada").execute()
            for ca in ativas.data:
                st.write(f"ID {ca['id']} - {ca['passageiro']} | {ca['status']}")
                if st.button(f"Encerrar #{ca['id']}", key=f"adm_f_{ca['id']}"):
                    conn.table("corridas").update({"status": "Finalizada"}).eq("id", ca['id']).execute()
                    st.rerun()
