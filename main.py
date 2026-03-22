import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_js_eval import get_geolocation
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import urllib.parse

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")
conn = st.connection("supabase", type=SupabaseConnection)

# Atualização automática a cada 5 segundos para sincronizar as telas
st_autorefresh(interval=5000, key="global_refresh")

# --- INICIALIZAÇÃO DO ESTADO DO USUÁRIO ---
if "user_cpf" not in st.session_state:
    st.session_state.user_cpf = None
if "user_nome" not in st.session_state:
    st.session_state.user_nome = None
if "user_tipo" not in st.session_state:
    st.session_state.user_tipo = None

def logout():
    if st.session_state.user_cpf:
        try:
            conn.table("usuarios").update({"logado": False}).eq("cpf", st.session_state.user_cpf).execute()
        except: pass
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --- TELA DE ACESSO (LOGIN / CADASTRO) ---
if not st.session_state.user_cpf:
    st.title("🛡️ CORRIDA PROTEGIDA")
    t1, t2 = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    
    with t2:
        st.subheader("Criar Nova Conta")
        tp = st.radio("Eu sou:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="reg_perfil")
        n = st.text_input("Nome Completo", key="reg_n_input")
        c = st.text_input("CPF (apenas números)", key="reg_c_input")
        pix = st.text_input("Chave PIX", key="reg_pix_input") if tp == "Sou Motorista" else ""
        s = st.text_input("Senha", type="password", key="reg_s_input")
        
        if st.button("Finalizar Cadastro", key="reg_btn_submit"):
            if n and c and s:
                conn.table("usuarios").insert([{"tipo": tp, "nome": n, "cpf": c, "senha": s, "chave_pix": pix, "preco_km": 2.0}]).execute()
                st.success("✅ Cadastrado! Agora você pode Entrar.")
            else: st.warning("Preencha todos os campos obrigatórios!")

    with t1:
        st.subheader("Acessar Painel")
        tl = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista", "Administrador"], horizontal=True, key="log_perfil")
        lc = st.text_input("CPF", key="log_c_input")
        ls = st.text_input("Senha", type="password", key="log_s_input")
        
        if st.button("Acessar", key="log_btn_submit"):
            r = conn.table("usuarios").select("*").eq("cpf", lc).eq("senha", ls).eq("tipo", tl).execute()
            if r.data and len(r.data) > 0:
                u = r.data[0]
                st.session_state.user_cpf = u['cpf']
                st.session_state.user_nome = u['nome']
                st.session_state.user_tipo = u['tipo']
                conn.table("usuarios").update({"logado": True}).eq("cpf", u['cpf']).execute()
                st.rerun()
            else: st.error("Dados incorretos ou perfil não autorizado.")

# --- PAINEL LOGADO ---
else:
    # --- BARRA LATERAL ---
    st.sidebar.write(f"👤 **{st.session_state.user_nome}**")
    
    # MODO TESTE (Apenas para ADM)
    perfil_ativo = st.session_state.user_tipo
    if st.session_state.user_tipo == "Administrador":
        st.sidebar.divider()
        st.sidebar.subheader("🛠️ Seletor de Visão")
        perfil_ativo = st.sidebar.radio(
            "Ver como:", 
            ["Administrador", "Sou Passageiro", "Sou Motorista"],
            index=0
        )
    
    st.sidebar.divider()
    st.sidebar.button("🚪 Sair da Conta", on_click=logout, key="btn_logout_sidebar")

    # --- 1. VISÃO PASSAGEIRO ---
    if perfil_ativo == "Sou Passageiro":
        st.title("Painel do Passageiro 📍")
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        
        if res.data and len(res.data) > 0:
            c = res.data[0]
            st.info(f"Status Atual: **{c['status']}**")
            
            if c['status'] == "Confirmada" and c.get('lat_motorista'):
                st.subheader(f"🚖 {c['motorista_nome']} está a caminho!")
                df_mapa = pd.DataFrame({'lat': [c['lat_motorista']], 'lon': [c['lon_motorista']]})
                st.map(df_mapa)
                
                m_info = conn.table("usuarios").select("chave_pix").eq("nome", c['motorista_nome']).execute()
                if m_info.data: st.warning(f"PIX do Motorista: `{m_info.data[0]['chave_pix']}`")

            if st.button("Cancelar Corrida ❌", key=f"pax_del_{c['id']}"):
                conn.table("corridas").delete().eq("id", c['id']).execute()
                st.rerun()
        else:
            o = st.text_input("Onde você está?", key="input_origem")
            d = st.text_input("Para onde vamos?", key="input_destino")
            v = st.number_input("Sua oferta (R$)", min_value=5.0, value=15.0, key="input_valor")
            if st.button("SOLICITAR AGORA 🚀", key="btn_solicitar_pax"):
                conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": o, "ponto_destino": d, "valor_total": v, "status": "Buscando"}]).execute()
                st.rerun()

    # --- 2. VISÃO MOTORISTA ---
    elif perfil_ativo == "Sou Motorista":
        st.title("Painel do Motorista 🛣️")
        
        loc = get_geolocation()
        if loc:
            lat_m, lon_m = loc['coords']['latitude'], loc['coords']['longitude']
            conn.table("corridas").update({"lat_motorista": lat_m, "lon_motorista": lon_m}).eq("motorista_nome", st.session_state.user_nome).eq("status", "Confirmada").execute()

        st.subheader("Chamadas Disponíveis")
        corridas = conn.table("corridas").select("*").in_("status", ["Buscando", "Negociando"]).execute()
        
        if not corridas.data:
            st.info("Nenhuma chamada no momento. Aguarde novos pedidos...")

        for r in corridas.data:
            with st.container(border=True):
                st.write(f"👤 **{r['passageiro']}** | Oferta: R$ {r['valor_total']:.2f}")
                st.caption(f"De: {r['ponto_origem']} ➡️ {r['ponto_destino']}")
                
                # LINK PARA ABRIR APP WAZE NO CELULAR
                addr = urllib.parse.quote(r['ponto_destino'])
                st.markdown(f'<a href="waze://?q={addr}&navigate=yes"><button style="width:100%; background-color:#33CCFF; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer; margin-bottom:10px;">🚀 ABRIR NO APP WAZE</button></a>', unsafe_allow_html=True)
                
                if st.button(f"Aceitar Corrida #{r['id']}", key=f"acc_mot_{r['id']}", use_container_width=True):
                    conn.table("corridas").update({"status": "Confirmada", "motorista_nome": st.session_state.user_nome}).eq("id", r['id']).execute()
                    st.rerun()

    # --- 3. VISÃO ADMINISTRADOR ---
    elif perfil_ativo == "Administrador":
        st.title("🛡️ Painel de Controle ADM")
        t_u, t_c, t_f = st.tabs(["👥 Usuários", "🚖 Todas as Corridas", "📊 Financeiro"])

        with t_u:
            users = conn.table("usuarios").select("*").execute()
            if users.data:
                df_u = pd.DataFrame(users.data)
                cols = [c for c in ['nome', 'tipo', 'cpf', 'logado'] if c in df_u.columns]
                st.dataframe(df_u[cols], use_container_width=True)
                
                u_del = st.selectbox("Selecione usuário para remover:", df_u['nome'], key="sel_user_del")
                if st.button("Remover Usuário Permanentemente", type="primary", key="btn_adm_del"):
                    conn.table("usuarios").delete().eq("nome", u_del).execute()
                    st.rerun()

        with t_c:
            cor_ativas = conn.table("corridas").select("*").neq("status", "Finalizada").execute()
            if cor_ativas.data:
                for ca in cor_ativas.data:
                    st.write(f"**ID {ca['id']}** | {ca['passageiro']} ➡️ {ca['motorista_nome'] or '---'} | Status: {ca['status']}")
                    if st.button(f"Forçar Encerramento #{ca['id']}", key=f"adm_force_{ca['id']}"):
                        conn.table("corridas").update({"status": "Finalizada"}).eq("id", ca['id']).execute()
                        st.rerun()
            else: st.info("Nenhuma corrida ativa no momento.")

        with t_f:
            fina = conn.table("corridas").select("valor_total").eq("status", "Finalizada").execute()
            total = sum(i['valor_total'] for i in fina.data) if fina.data else 0
            st.metric("Volume Total de Corridas (Finalizadas)", f"R$ {total:.2f}")
