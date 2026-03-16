import streamlit as st
from st_supabase_connection import SupabaseConnection
from streamlit_js_eval import get_geolocation
import pandas as pd
import urllib.parse

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Corrida Protegida 🛡️", layout="centered")
conn = st.connection("supabase", type=SupabaseConnection)

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
        pix = st.text_input("Chave PIX (para receber)", key="reg_pix") if tp == "Sou Motorista" else ""
        s = st.text_input("Senha", type="password", key="reg_s")
        
        if st.button("Finalizar Cadastro", key="reg_btn"):
            if n and c and s:
                conn.table("usuarios").insert([{"tipo": tp, "nome": n, "cpf": c, "senha": s, "chave_pix": pix, "preco_km": 2.0}]).execute()
                st.success("✅ Cadastrado! Vá para a aba Entrar.")
            else: st.warning("Preencha todos os campos!")

    with t1:
        st.subheader("Acessar Painel")
        tl = st.radio("Entrar como:", ["Sou Passageiro", "Sou Motorista"], horizontal=True, key="log_tp")
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
            else: st.error("Dados incorretos.")

# --- PAINEL LOGADO ---
else:
    st.sidebar.write(f"👤 **{st.session_state.user_nome}**")
    st.sidebar.button("🚪 Sair", on_click=logout, key="side_out")
    if st.sidebar.button("🔄 Atualizar App", key="side_ref"): st.rerun()

    # --- VISÃO PASSAGEIRO ---
    if st.session_state.user_tipo == "Sou Passageiro":
        st.title("Painel do Passageiro 📍")
        res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
        
        if res.data:
            c = res.data[0]
            st.info(f"Status: **{c['status']}**")
            
            # Mapa do Motorista vindo (Acompanhamento em tempo real)
            if c['status'] == "Confirmada" and c['lat_motorista']:
                st.subheader(f"🚖 {c['motorista_nome']} está chegando!")
                df_mapa = pd.DataFrame({'lat': [c['lat_motorista']], 'lon': [c['lon_motorista']]})
                st.map(df_mapa, zoom=14)
                
                # Chave PIX do Motorista (Busca na tabela usuários)
                m_info = conn.table("usuarios").select("chave_pix").eq("nome", c['motorista_nome']).execute()
                if m_info.data:
                    st.warning(f"PIX para pagamento: `{m_info.data[0]['chave_pix']}`")

            if st.button("Cancelar Corrida ❌", key="pax_cancel"):
                conn.table("corridas").delete().eq("id", c['id']).execute()
                st.rerun()
        else:
            o = st.text_input("Origem (Onde você está?)", key="pax_o")
            d = st.text_input("Destino (Para onde vamos?)", key="pax_d")
            v = st.number_input("Sua oferta (R$)", min_value=5.0, value=15.0, key="pax_v")
            if st.button("SOLICITAR AGORA 🚀", key="pax_btn"):
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
        
        # GPS EM TEMPO REAL (Envia para o banco se estiver em corrida)
        loc = get_geolocation()
        if loc:
            lat_m, lon_m = loc['coords']['latitude'], loc['coords']['longitude']
            conn.table("corridas").update({"lat_motorista": lat_m, "lon_motorista": lon_m}).eq("motorista_nome", st.session_state.user_nome).eq("status", "Confirmada").execute()

        # Configuração de Preço/KM
        u_info = conn.table("usuarios").select("preco_km").eq("cpf", st.session_state.user_cpf).execute()
        preco_atual = float(u_info.data[0]['preco_km'] if u_info.data else 2.0)
        p_km = st.slider("Seu valor por KM", 1.5, 6.0, preco_atual, step=0.1)
        if st.button("Salvar Valor/KM", key="save_km"):
            conn.table("usuarios").update({"preco_km": p_km}).eq("cpf", st.session_state.user_cpf).execute()

        # Lista de Chamadas
        st.subheader("Chamadas Disponíveis")
        corridas = conn.table("corridas").select("*").in_("status", ["Buscando", "Negociando"]).execute()
        
        if not corridas.data:
            st.info("Nenhuma chamada no momento.")
        
        for r in corridas.data:
            with st.container(border=True):
                st.write(f"👤 **{r['passageiro']}** | Oferta: R$ {r['valor_total']:.2f}")
                st.caption(f"De: {r['ponto_origem']} ➡️ {r['ponto_destino']}")
                
                # Link Waze
                dest_url = urllib.parse.quote(r['ponto_destino'])
                st.markdown(f"[🚀 Abrir Waze](https://www.waze.com{dest_url}&navigate=yes)")

                # Calculadora de Proposta
                dist = st.number_input(f"Distância (km) p/ #{r['id']}", 0.1, key=f"dist_{r['id']}")
                calc_val = dist * p_km
                st.write(f"Sugestão pelo seu KM: **R$ {calc_val:.2f}**")
                
                c1, c2 = st.columns(2)
                with c1:
                    if st.button(f"ACEITAR ✅", key=f"acc_{r['id']}"):
                        conn.table("corridas").update({
                            "status": "Confirmada", 
                            "motorista_nome": st.session_state.user_nome,
                            "distancia_km": dist
                        }).eq("id", r['id']).execute()
                        st.rerun()
                with c2:
                    if st.button(f"PROPOSTA R${calc_val:.2f}", key=f"prop_{r['id']}"):
                        conn.table("corridas").update({
                            "valor_total": calc_val, 
                            "status": "Negociando", 
                            "motorista_nome": st.session_state.user_nome
                        }).eq("id", r['id']).execute()
                        st.rerun()
                
                if r['status'] == "Confirmada" and r['motorista_nome'] == st.session_state.user_nome:
                    if st.button("🏁 FINALIZAR CORRIDA", key=f"fin_{r['id']}"):
                        conn.table("corridas").update({"status": "Finalizada"}).eq("id", r['id']).execute()
                        st.rerun()
