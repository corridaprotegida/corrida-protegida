# --- VISÃO PASSAGEIRO (DENTRO DO IF user_tipo == "Sou Passageiro") ---
if st.session_state.user_tipo == "Sou Passageiro":
    st.title("Painel do Passageiro 📍")
    
    # Busca corrida ativa
    res = conn.table("corridas").select("*").eq("passageiro", st.session_state.user_nome).neq("status", "Finalizada").execute()
    
    if res.data:
        c = res.data[0]
        st.info(f"Status: **{c['status']}**")

        # --- MAPA DE ACOMPANHAMENTO ---
        if c['status'] == "Confirmada" and c['lat_motorista'] and c['lon_motorista']:
            st.subheader(f"🚖 {c['motorista_nome']} está a caminho!")
            
            # Criar DataFrame para o mapa do Streamlit
            df_moto = pd.DataFrame({
                'lat': [c['lat_motorista']],
                'lon': [c['lon_motorista']]
            })
            
            # Mostra o mapa centralizado no motorista
            st.map(df_moto, zoom=14)
            
            # Exibir Chave PIX do Motorista (puxando da tabela usuários)
            mot_info = conn.table("usuarios").select("chave_pix").eq("nome", c['motorista_nome']).execute()
            if mot_info.data:
                st.warning(f"Chave PIX para pagamento: `{mot_info.data[0]['chave_pix']}`")

        # --- BOTÕES DE AÇÃO ---
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            if st.button("Cancelar Corrida ❌", key="btn_pax_cancel"):
                conn.table("corridas").delete().eq("id", c['id']).execute()
                st.rerun()
        with col_c2:
            if st.button("🔄 Atualizar Mapa", key="btn_pax_refresh"):
                st.rerun()

    else:
        # Formulário para nova corrida (como já estava no código anterior)
        st.subheader("Para onde vamos?")
        o = st.text_input("Origem", key="pax_ori")
        d = st.text_input("Destino", key="pax_dest")
        v = st.number_input("Oferta (R$)", min_value=5.0, value=15.0, key="pax_val")
        if st.button("SOLICITAR AGORA 🚀", key="pax_go"):
            conn.table("corridas").insert([{"passageiro": st.session_state.user_nome, "ponto_origem": o, "ponto_destino": d, "valor_total": v, "status": "Buscando"}]).execute()
            st.rerun()
