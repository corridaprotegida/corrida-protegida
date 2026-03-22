import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_js_eval import get_geolocation
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import urllib.parse

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")
conn = st.connection("supabase", type=SupabaseConnection)

# Atualização automática a cada 5 segundos para sincronizar todos os painéis
st_autorefresh(interval=5000, key="global_refresh")

# --- INICIALIZAÇÃO DO ESTADO (EVITA NAMEERROR) ---
if "user_cpf" not in st.session_state:
    st.session_state.user_cpf = None
if "user_nome" not in st.session_state:
    st.session_state.user_nome = None
if "user_tipo" not in st.session_state:
    st.session_state.user_tipo = None

def logout():
    if st.session_state.user_cpf:
        conn.table("usuarios").update({"logado": False}).eq("cpf", st.session_state.user_cpf).execute()
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --- TELA DE ACESSO (LOGIN / CADASTRO) ---
if not st.session_state.user_cpf:
    st.title("🛡️ CORRIDA PROTEGIDA")
    t1, t2 = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    
    with t2:
        st.subheader("Criar Nova Conta")
        tp = st.radio("Eu sou:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="reg_tp")
        n = st.text_input("Nome Completo", key="reg_n")
        c = st.text_input("CPF (apenas números)", key="reg_c")
        pix = st.text_input("Chave PIX", key="reg_pix") if tp == "Sou Motorista" else ""
        s = st.text_input("Senha", type="password", key="reg_s")
        
        if st.button("Finalizar Cadastro", key="reg_btn"):
            if n and c and s:
                conn.table("usuarios").insert([{"tipo": tp, "nome": n, "cpf": c, "senha": s, "chave_pix": pix, "preco_km": 2.0}]).execute()
                st.success("✅ Cadastrado! Vá para a aba Entrar.")
            else: st.warning("Preencha todos os campos!")

    with t1:
        st.subheader("Acessar Painel")
        tl = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista", "Administrador"], horizontal=True, key="log_tp")
        lc = st.text_input("CPF", key="log_c")
        ls = st.text_input("Senha", type="password", key="log_s")
        
        if st.button("Acessar", key="log_btn"):
            r = conn.table("usuarios").select("*").eq("cpf", lc).eq("senha", ls).eq("tipo", tl).execute()
            if r.data:
                u = r.data[0]
                st.session_state.user_cpf = u['cpf']
                st.session_state.user_nome = u['nome']
                st.session_state.user_tipo = u['tipo']
                conn.table("usuarios").update({"logado": True}).eq("cpf", u['cpf']).execute()
                st.rerun()
            else: st.error("Dados incorretos ou perfil não autorizado.")

# --- PAINEL LOGADO ---
else:
    st.sidebar.write(f"👤 **{st.session_state.user_nome}**")
    st.sidebar.caption(f"Perfil: {st.session_state.user_tipo}")
    st.sidebar.button("🚪 Sair", on_click=logout, key="side_logout")

    # --- 1. VISÃO PASSAGEIRO ---
    if st.session_state.user_tipo == "Sou Passageiro":
        st.title("Painel do Passageiro 📍")
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        
        if res.data:
            c = res.data[0]
            st.info(f"Status Atual: **{c['status']}**")
            
            if c['status'] == "Confirmada" and c['lat_motorista']:
                st.subheader(f"🚖 {c['motorista_nome']} está a caminho!")
                df_mapa = pd.DataFrame({'lat': [c['lat_motorista']], 'lon': [c['lon_motorista']]})
                st.map(df_mapa)
                
                m_info = conn.table("usuarios").select("chave_pix").eq("nome", c['motorista_nome']).execute()
                if m_info.data:
                    st.warning(f"Pagamento PIX para o motorista: `{m_info.data[0]['chave_pix']}`")

            if st.button("Cancelar Corrida ❌", key="pax_cancel"):
                conn.table("corridas").delete().eq("id", c['id']).execute()
                st.rerun()
        else:
            o = st.text_input("Onde você está?", key="pax_o")
            d = st.text_input("Para onde vamos?", key="pax_d")
            v = st.number_input("Sua oferta (R$)", min_value=5.0, value=15.0, key="pax_v")
            if st.button("SOLICITAR AGORA 🚀", key="pax_go"):
                conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": o, "ponto_destino": d, "valor_total": v, "status": "Buscando"}]).execute()
                st.rerun()

    # --- 2. VISÃO MOTORISTA ---
    elif st.session_state.user_tipo == "Sou Motorista":
        st.title("Painel do Motorista 🛣️")
        
        loc = get_geolocation()
        if loc:
            lat_m, lon_m = loc['coords']['latitude'], loc['coords']['longitude']
            conn.table("corridas").update({"lat_motorista": lat_m, "lon_motorista": lon_m}).eq("motorista_nome", st.session_state.user_nome).eq("status", "Confirmada").execute()

        st.subheader("Chamadas Disponíveis")
        corridas = conn.table("corridas").select("*").in_("status", ["Buscando", "Negociando"]).execute()
        
        for r in corridas.data:
            with st.container(border=True):
                st.write(f"👤 **{r['passageiro']}** | Oferta: R$ {r['valor_total']:.2f}")
                st.caption(f"De: {r['ponto_origem']} ➡️ {r['ponto_destino']}")
                
                # WAZE DIRETO NO APP
                addr = urllib.parse.quote(r['ponto_destino'])
                st.markdown(f'<a href="waze://?q={addr}&navigate=yes"><button style="width:100%; background-color:#33CCFF; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer; margin-bottom:10px;">🚀 ABRIR NO APP WAZE</button></a>', unsafe_allow_html=True)
                
                if st.button(f"Aceitar Corrida #{r['id']}", key=f"acc_{r['id']}", use_container_width=True):
                    conn.table("corridas").update({"status": "Confirmada", "motorista_nome": st.session_state.user_nome}).eq("id", r['id']).execute()
                    st.rerun()

    # --- 3. VISÃO ADMINISTRADOR ---
    elif st.session_state.user_tipo == "Administrador":
        st.title("🛡️ Painel de Controle ADM")
        t_u, t_c, t_f = st.tabs(["👥 Usuários", "🚖 Corridas", "📊 Financeiro"])

        with t_u:
            users = conn.table("usuarios").select("*").execute()
            df_u = pd.DataFrame(users.data)
            st.dataframe(df_u[['nome', 'tipo', 'cpf', 'logado']])
            u_del = st.selectbox("Remover Usuário:", df_u['nome'], key="sel_del")
            if st.button("Remover", type="primary"):
                conn.table("usuarios").delete().eq("nome", u_del).execute()
                st.rerun()

        with t_c:
            cor_ativas = conn.table("corridas").select("*").neq("status", "Finalizada").execute()
            for ca in cor_ativas.data:
                st.write(f"ID {ca['id']} - {ca['passageiro']} (R$ {ca['valor_total']}) - {ca['status']}")
                if st.button(f"Encerrar #{ca['id']}", key=f"adm_f_{ca['id']}"):
                    conn.table("corridas").update({"status": "Finalizada"}).eq("id", ca['id']).execute()
                    st.rerun()

        with t_f:
            fina = conn.table("corridas").select("valor_total").eq("status", "Finalizada").execute()
            total = sum(i['valor_total'] for i in fina.data) if fina.data else 0
            st.metric("Total Movimentado", f"R$ {total:.2f}")
