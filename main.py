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
                conn.table("usuarios").insert([{"tipo": tp, "nome": n, "cpf": c, "senha": s, "preco_km": 1.70}]).execute()
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
            else: st.error("Dados incorretos ou usuário não encontrado.")

# --- PAINEL LOGADO ---
else:
    st.sidebar.write(f"👤 **{st.session_state.user_nome}**")
    st.sidebar.write(f"🏷️ {st.session_state.user_tipo}")
    if st.sidebar.button("🔄 ATUALIZAR", key="side_refresh"): st.rerun()
    st.sidebar.button("🚪 Sair", on_click=logout, key="side_logout")

    # --- VISÃO PASSAGEIRO ---
    if st.session_state.user_tipo == "Sou Passageiro":
        st.title("Painel do Passageiro 📍")
        
        # Busca corridas ativas do passageiro
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        
        if res.data:
            c = res.data[0]
            st.info(f"Status Atual: **{c['status']}**")
            
            if c['status'] == "Buscando":
                st.warning("Aguardando motoristas interessados...")
                if st.button("Cancelar Chamada ❌"):
                    conn.table("corridas").delete().eq("id", c['id']).execute()
                    st.rerun()

            elif c['status'] == "Negociando":
                st.subheader("⚠️ Nova Proposta Recebida!")
                st.write(f"O motorista **{c['motorista_nome']}** sugeriu um novo valor.")
                st.metric("VALOR DO MOTORISTA", f"R$ {c['valor_total']:.2f}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("ACEITAR ✅", use_container_width=True):
                        conn.table("corridas").update({"status": "Confirmada"}).eq("id", c['id']).execute()
                        st.rerun()
                with col2:
                    if st.button("RECUSAR/CANCELAR ❌", use_container_width=True):
                        conn.table("corridas").delete().eq("id", c['id']).execute()
                        st.rerun()

            elif c['status'] == "Confirmada":
                st.success(f"Motorista {c['motorista_nome']} está a caminho!")
                st.metric("VALOR FECHADO", f"R$ {c['valor_total']:.2f}")
                st.write(f"📍 De: {c['ponto_origem']} \n🏁 Para: {c['ponto_destino']}")
        
        else:
            # Formulário para nova corrida
            with st.container(border=True):
                o = st.text_input("Onde você está?", placeholder="Ex: Rua das Flores, 123")
                d = st.text_input("Para onde vamos?", placeholder="Ex: Shopping Central")
                v = st.number_input("Sua oferta inicial (R$)", min_value=5.0, value=15.0, step=1.0)
                
                if st.button("SOLICITAR CORRIDA 🚀", use_container_width=True):
                    if o and d:
                        conn.table("corridas").insert([{
                            "passageiro": st.session_state.user_nome, 
                            "ponto_origem": o, 
                            "ponto_destino": d, 
                            "valor_total": v,
                            "status": "Buscando"
                        }]).execute()
                        st.rerun()

    # --- VISÃO MOTORISTA ---
    elif st.session_state.user_tipo == "Sou Motorista":
        st.title("Painel do Motorista 🛣️")
        
        # Verifica se o motorista já está em uma corrida confirmada
        minha_corrida = conn.table("corridas").select("*").eq("motorista_nome", st.session_state.user_nome).eq("status", "Confirmada").execute()
        
        if minha_corrida.data:
            c = minha_corrida.data[0]
            st.success(f"VIAGEM EM ANDAMENTO COM {c['passageiro']}")
            st.write(f"💰 Valor: R$ {c['valor_total']:.2f}")
            
            end_dest = urllib.parse.quote(c['ponto_destino'])
            st.markdown(f"""
                <div style="display: flex; flex-direction: column; gap: 10px; margin-bottom: 20px;">
                    <a href="waze://?q={end_dest}&navigate=yes" style="text-decoration: none;">
                        <div style="background:#33ccff;color:white;padding:15px;border-radius:10px;text-align:center;font-weight:bold;">🚗 ABRIR WAZE</div>
                    </a>
                    <a href="https://www.google.com{end_dest}" style="text-decoration: none;">
                        <div style="background:#4285F4;color:white;padding:15px;border-radius:10px;text-align:center;font-weight:bold;">📍 GOOGLE MAPS</div>
                    </a>
                </div>
            """, unsafe_allow_html=True)
            
            if st.button("🏁 FINALIZAR CORRIDA", use_container_width=True, type="primary"):
                conn.table("corridas").update({"status": "Finalizada"}).eq("id", c['id']).execute()
                st.rerun()
        
        else:
            st.subheader("Chamadas Disponíveis")
            corridas = conn.table("corridas").select("*").in_("status", ["Buscando", "Negociando"]).execute()
            
            if not corridas.data:
                st.info("Nenhuma chamada no momento. Aguarde...")
            
            for r in corridas.data:
                with st.container(border=True):
                    st.write(f"👤 **{r['passageiro']}**")
                    st.write(f"📍 {r['ponto_origem']} ➡️ {r['ponto_destino']}")
                    st.write(f"💰 Oferta atual: **R$ {r['valor_total']:.2f}**")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"ACEITAR R${r['valor_total']}", key=f"acc_{r['id']}"):
                            conn.table("corridas").update({
                                "status": "Confirmada", 
                                "motorista_nome": st.session_state.user_nome
                            }).eq("id", r['id']).execute()
                            st.rerun()
                    
                    with col2:
                        contra = st.number_input("Contraproposta", min_value=float(r['valor_total']+1), value=float(r['valor_total']+3), key=f"v_{r['id']}")
                        if st.button(f"ENVIAR R${contra}", key=f"prop_{r['id']}"):
                            conn.table("corridas").update({
                                "valor_total": contra,
                                "status": "Negociando",
                                "motorista_nome": st.session_state.user_nome
                            }).eq("id", r['id']).execute()
                            st.rerun()

