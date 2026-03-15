import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_js_eval import streamlit_js_eval
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
            else: st.error("Dados incorretos.")

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
            if c['status'] == "Confirmada":
                st.success(f"Motorista {c.get('motorista_nome')} aceitou o seu preço e está a caminho!")
                st.metric("VALOR COMBINADO", f"R$ {c['valor_total']:.2f}")
        else:
            o = st.text_input("Onde você está?", key="psg_orig")
            d = st.text_input("Para onde vamos?", key="psg_dest")
            v_sugerido = st.number_input("Quanto deseja oferecer pela corrida? (R$)", min_value=5.0, value=15.0, step=1.0, key="psg_val")
            
            if st.button("BUSCAR MOTORISTAS 🚀", key="btn_busca"):
                if o and d:
                    conn.table("corridas").insert([{
                        "passageiro": st.session_state.user_nome, 
                        "ponto_origem": o, 
                        "ponto_destino": d, 
                        "valor_total": v_sugerido,
                        "status": "Buscando"
                    }]).execute()
                    st.rerun()

    # --- VISÃO MOTORISTA ---
    elif st.session_state.user_tipo == "Sou Motorista":
        st.title("Painel do Motorista 🛣️")
        
        # 1. Configurar Tarifa (Opcional agora que passageiro sugere)
        perf = conn.table("usuarios").select("preco_km").eq("cpf", st.session_state.user_cpf).execute()
        taxa_atual = perf.data[0]['preco_km'] if perf.data else 1.70
        st.info(f"Sua mensalidade: R$ 52,99 | Sua base: R$ {taxa_atual:.2f}/km")

        # 2. Corridas Disponíveis com Preço do Passageiro
        st.write("---")
        corridas = conn.table("corridas").select("*").eq("status", "Buscando").execute()
        if not corridas.data:
            st.info("Nenhuma chamada nova. Clique em Atualizar.")
        
        for r in corridas.data:
            with st.container(border=True):
                st.write(f"👤 **{r['passageiro']}**")
                st.write(f"📍 DE: {r['ponto_origem']}")
                st.write(f"🏁 PARA: {r['ponto_destino']}")
                st.write(f"💰 PASSAGEIRO OFERECE: **R$ {r['valor_total']:.2f}**")
                
                if st.button(f"ACEITAR VALOR E INICIAR #{r['id']}", key=f"btn_acc_{r['id']}"):
                    conn.table("corridas").update({
                        "status": "Confirmada", 
                        "motorista_nome": st.session_state.user_nome
                    }).eq("id", r['id']).execute()
                    st.rerun()

        # 3. Viagens Confirmadas (Botões Diretos para APPS)
        st.write("---")
        conf = conn.table("corridas").select("*").eq("motorista_nome", st.session_state.user_nome).eq("status", "Confirmada").execute()
        if conf.data:
            for c in conf.data:
                st.success(f"VIAGEM CONFIRMADA COM {c['passageiro']}")
                end = urllib.parse.quote(c['ponto_origem'])
                
                # LINKS QUE FORÇAM A ABERTURA DO APLICATIVO INSTALADO
                link_waze = f"waze://?q={end}&navigate=yes"
                link_google = f"google.navigation:q={end}"
                
                st.markdown(f"""
                <div style="display: flex; flex-direction: column; gap: 10px;">
                    <a href="{link_waze}" style="text-decoration: none;">
                        <div style="background:#33ccff;color:white;padding:15px;border-radius:10px;text-align:center;font-weight:bold;cursor:pointer;">
                            🚗 ABRIR NO APP WAZE
                        </div>
                    </a>
                    <a href="{link_google}" style="text-decoration: none;">
                        <div style="background:#4285F4;color:white;padding:15px;border-radius:10px;text-align:center;font-weight:bold;cursor:pointer;">
                            📍 ABRIR NO APP GOOGLE MAPS
                        </div>
                    </a>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"🏁 FINALIZAR CORRIDA #{c['id']}", key=f"btn_fin_{c['id']}"):
                    conn.table("corridas").update({"status": "Finalizada"}).eq("id", c['id']).execute()
                    st.rerun()
