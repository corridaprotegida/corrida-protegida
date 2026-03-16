import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_js_eval import streamlit_js_eval
import pandas as pd
import urllib.parse

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")
conn = st.connection("supabase", type=SupabaseConnection)

# --- ESTADO DE LOGIN ---
if "user_cpf" not in st.session_state:
    st.session_state.user_cpf = None

def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --- LOGIN / CADASTRO ---
if not st.session_state.user_cpf:
    st.title("🛡️ CORRIDA PROTEGIDA")
    t1, t2 = st.tabs(["🔐 Entrar", "📝 Cadastrar"])
    
    with t2:
        st.subheader("Criar Nova Conta")
        tp = st.radio("Eu sou:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="cad_tipo")
        n = st.text_input("Nome Completo", key="cad_nome")
        c = st.text_input("CPF (apenas números)", key="cad_cpf")
        s = st.text_input("Senha", type="password", key="cad_senha")
        if st.button("Finalizar Cadastro", key="btn_cad"):
            if n and c and s:
                conn.table("usuarios").insert([{"tipo": tp, "nome": n, "cpf": c, "senha": s, "preco_km": 2.00}]).execute()
                st.success("✅ Cadastrado! Agora vá na aba Entrar.")
            else: st.warning("Preencha todos os campos!")

    with t1:
        st.subheader("Acessar Painel")
        tl = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="log_tipo")
        lc = st.text_input("CPF", key="log_cpf")
        ls = st.text_input("Senha", type="password", key="log_senha")
        if st.button("Acessar", key="btn_log"):
            r = conn.table("usuarios").select("*").eq("cpf", lc).eq("senha", ls).eq("tipo", tl).execute()
            if r.data:
                user = r.data[0]
                st.session_state.user_cpf = user['cpf']
                st.session_state.user_nome = user['nome']
                st.session_state.user_tipo = user['tipo']
                st.rerun()
            else: st.error("Dados incorretos.")

# --- PAINEL LOGADO ---
else:
    st.sidebar.write(f"👤 **{st.session_state.user_nome}**")
    if st.sidebar.button("🔄 ATUALIZAR", key="side_refresh"): st.rerun()
    st.sidebar.button("🚪 Sair", on_click=logout, key="side_logout")

    # --- VISÃO PASSAGEIRO ---
    if st.session_state.user_tipo == "Sou Passageiro":
        st.title("Painel do Passageiro 📍")
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        
        if res.data:
            c = res.data[0]
            if c['status'] == "Buscando":
                st.info("Aguardando motoristas...")
                if st.button("Cancelar Chamada ❌"):
                    conn.table("corridas").delete().eq("id", c['id']).execute()
                    st.rerun()
            elif c['status'] == "Negociando":
                st.warning(f"O motorista {c['motorista_nome']} propôs R$ {c['valor_total']:.2f}")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("ACEITAR ✅"):
                        conn.table("corridas").update({"status": "Confirmada"}).eq("id", c['id']).execute()
                        st.rerun()
                with col2:
                    if st.button("RECUSAR ❌"):
                        conn.table("corridas").delete().eq("id", c['id']).execute()
                        st.rerun()
            elif c['status'] == "Confirmada":
                st.success(f"Motorista {c['motorista_nome']} a caminho! Valor: R$ {c['valor_total']:.2f}")
        else:
            o = st.text_input("Onde você está?")
            d = st.text_input("Para onde vamos?")
            v = st.number_input("Sua oferta (R$)", min_value=5.0, value=15.0)
            if st.button("SOLICITAR 🚀"):
                conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": o, "ponto_destino": d, "valor_total": v, "status": "Buscando"}]).execute()
                st.rerun()

    # --- VISÃO MOTORISTA ---
    elif st.session_state.user_tipo == "Sou Motorista":
        st.title("Painel do Motorista 🛣️")
        
        # --- 1. CONFIGURAÇÃO DE GANHO POR KM ---
        with st.expander("⚙️ Configurar Meu Ganho por KM"):
            ganho_km = st.slider("Quanto você quer ganhar por KM?", 1.70, 7.00, 2.50, step=0.10)
            st.caption(f"Seu valor base atual: R$ {ganho_km:.2f}/km")

        minha_corrida = conn.table("corridas").select("*").eq("motorista_nome", st.session_state.user_nome).eq("status", "Confirmada").execute()
        
        if minha_corrida.data:
            c = minha_corrida.data[0]
            st.success(f"EM VIAGEM COM {c['passageiro']}")
            if st.button("🏁 FINALIZAR CORRIDA"):
                conn.table("corridas").update({"status": "Finalizada"}).eq("id", c['id']).execute()
                st.rerun()
        else:
            st.subheader("Chamadas Disponíveis")
            corridas = conn.table("corridas").select("*").in_("status", ["Buscando", "Negociando"]).execute()
            
            for r in corridas.data:
                with st.container(border=True):
                    st.write(f"👤 **{r['passageiro']}** | Oferta: **R$ {r['valor_total']:.2f}**")
                    st.write(f"📍 {r['ponto_origem']} ➡️ {r['ponto_destino']}")
                    
                    # Links para o Waze ver a distância real
                    end_dest = urllib.parse.quote(r['ponto_destino'])
                    st.markdown(f"[🔍 Ver distância no Waze](waze://?q={end_dest})")

                    # --- 2. CALCULADORA DE PROPOSTA ---
                    st.write("---")
                    st.write("🧮 **Calculadora de Contraproposta**")
                    distancia = st.number_input(f"Distância da viagem (km) para #{r['id']}", min_value=0.1, step=0.1, key=f"dist_{r['id']}")
                    valor_calc = distancia * ganho_km
                    st.info(f"Sugestão baseada no seu KM: **R$ {valor_calc:.2f}**")

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"ACEITAR R${r['valor_total']}", key=f"acc_{r['id']}"):
                            conn.table("corridas").update({"status": "Confirmada", "motorista_nome": st.session_state.user_nome}).eq("id", r['id']).execute()
                            st.rerun()
                    with col2:
                        contra = st.number_input("Valor da Proposta (R$)", value=float(max(r['valor_total'], valor_calc)), key=f"v_{r['id']}")
                        if st.button(f"ENVIAR PROPOSTA", key=f"prop_{r['id']}"):
                            conn.table("corridas").update({"valor_total": contra, "status": "Negociando", "motorista_nome": st.session_state.user_nome}).eq("id", r['id']).execute()
                            st.rerun()
