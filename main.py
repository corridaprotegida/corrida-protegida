import streamlit as st
from st_supabase_connection import SupabaseConnection
import pandas as pd
import random
import urllib.parse

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")
conn = st.connection("supabase", type=SupabaseConnection)

# --- ESTADO DE LOGIN ---
if "user_cpf" not in st.session_state:
    st.session_state.user_cpf = None

def logout():
    st.session_state.user_cpf = None
    st.rerun()

# --- LOGIN / CADASTRO ---
if not st.session_state.user_cpf:
    st.title("🛡️ CORRIDA PROTEGIDA")
    t1, t2 = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    
    with t2:
        st.subheader("Criar Nova Conta")
        tp = st.radio("Eu sou:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="cad_tipo")
        n = st.text_input("Nome Completo", key="cad_nome")
        c = st.text_input("CPF (números)", key="cad_cpf")
        s = st.text_input("Senha", type="password", key="cad_senha")
        if st.button("Finalizar Cadastro", key="btn_cad"):
            if n and c and s:
                conn.table("usuarios").insert([{"tipo": tp, "nome": n, "cpf": c, "senha": s, "preco_km": 1.70}]).execute()
                st.success("✅ Cadastrado! Agora vá na aba Entrar.")
            else: st.warning("Preencha tudo!")

    with t1:
        st.subheader("Acessar Painel")
        tl = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="log_tipo")
        lc = st.text_input("CPF", key="log_cpf")
        ls = st.text_input("Senha", type="password", key="log_senha")
        if st.button("Acessar", key="btn_log"):
            r = conn.table("usuarios").select("*").eq("cpf", lc).eq("senha", ls).eq("tipo", tl).execute()
            if r.data and len(r.data) > 0:
                user = r.data[0]
                st.session_state.user_cpf = user['cpf']
                st.session_state.user_nome = user['nome']
                st.session_state.user_tipo = user['tipo']
                st.rerun()
            else: st.error("Dados incorretos ou perfil errado.")

# --- PAINEL LOGADO ---
else:
    st.sidebar.write(f"👤 **{st.session_state.user_nome}**")
    if st.sidebar.button("🔄 ATUALIZAR APP", key="side_refresh"): st.rerun()
    st.sidebar.button("🚪 Sair", on_click=logout, key="side_logout")

    # --- VISÃO PASSAGEIRO ---
    if st.session_state.user_tipo == "Sou Passageiro":
        st.title("Painel do Passageiro 📍")
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        
        if res.data and len(res.data) > 0:
            c = res.data[0]
            st.info(f"Status Atual: **{c['status']}**")
            
            if c['status'] == "Preço Sugerido":
                st.metric("VALOR OFERTADO", f"R$ {c['valor_total']:.2f}")
                col1, col2 = st.columns(2)
                if col1.button("✅ ACEITAR PREÇO", key=f"acc_p_{c['id']}"):
                    conn.table("corridas").update({"status": "Confirmada"}).eq("id", c['id']).execute()
                    st.rerun()
                if col2.button("❌ RECUSAR", key=f"rec_p_{c['id']}"):
                    conn.table("corridas").update({"status": "Finalizada"}).eq("id", c['id']).execute()
                    st.rerun()
            elif c['status'] == "Confirmada":
                st.success(f"O motorista {c.get('motorista_nome')} aceitou o preço e está a caminho!")
                st.info(f"De: {c['ponto_origem']} ➡️ Para: {c['ponto_destino']}")
        else:
            o = st.text_input("Onde você está?", key="psg_orig")
            d = st.text_input("Para onde vamos?", key="psg_dest")
            if st.button("BUSCAR MOTORISTAS", key="btn_busca"):
                if o and d:
                    conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": o, "ponto_destino": d, "status": "Buscando"}]).execute()
                    st.rerun()

    # --- VISÃO MOTORISTA ---
    elif st.session_state.user_tipo == "Sou Motorista":
        st.title("Painel do Motorista 🛣️")
        
        # 1. Configurar Ganho
        perf = conn.table("usuarios").select("preco_km").eq("cpf", st.session_state.user_cpf).execute()
        taxa_atual = perf.data[0]['preco_km'] if perf.data else 1.70
        taxa = st.number_input("Seu ganho por KM (Limite R$ 7,00)", 1.0, 7.0, float(taxa_atual), step=0.1, key="mot_taxa")
        if st.button("Salvar Tarifa", key="btn_save_taxa"):
            conn.table("usuarios").update({"preco_km": taxa}).eq("cpf", st.session_state.user_cpf).execute()
            st.success("Tarifa atualizada!")

        # 2. Corridas Disponíveis (Negociação)
        st.write("---")
        corridas = conn.table("corridas").select("*").eq("status", "Buscando").execute()
        if not corridas.data:
            st.info("Nenhuma chamada nova. Clique em Atualizar.")
        for r in corridas.data:
            with st.container(border=True):
                dist = round(random.uniform(2.0, 6.0), 2)
                valor = 5.0 + (dist * taxa)
                st.write(f"👤 **{r['passageiro']}** | 💰 Sugerido: **R$ {valor:.2f}**")
                if st.button(f"OFERTAR PREÇO #{r['id']}", key=f"btn_offer_{r['id']}"):
                    conn.table("corridas").update({
                        "status": "Preço Sugerido", "valor_total": valor, 
                        "motorista_nome": st.session_state.user_nome
                    }).eq("id", r['id']).execute()
                    st.rerun()

        # 3. Viagens Confirmadas (GPS)
        st.write("---")
        conf = conn.table("corridas").select("*").eq("motorista_nome", st.session_state.user_nome).eq("status", "Confirmada").execute()
        if conf.data:
            for c in conf.data:
                st.success(f"VIAGEM CONFIRMADA COM {c['passageiro']}")
                end = urllib.parse.quote(c['ponto_origem'])
                # Botão do Google Maps corrigido
                link_maps = f"https://www.google.com{end}"
                st.markdown(f'''<a href="{link_maps}" target="_blank" style="text-decoration:none;">
                                <div style="background:#4285F4;color:white;padding:12px;border-radius:8px;text-align:center;font-weight:bold;">
                                📍 ABRIR NAVEGAÇÃO GOOGLE MAPS</div></a>''', unsafe_allow_html=True)
                if st.button(f"🏁 FINALIZAR CORRIDA #{c['id']}", key=f"btn_fin_{c['id']}"):
                    conn.table("corridas").update({"status": "Finalizada"}).eq("id", c['id']).execute()
                    st.rerun()
