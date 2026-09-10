import streamlit as st
import pandas as pd
from datetime import datetime, date
import os

# Configuração da página
st.set_page_config(page_title="Gestão de Provas de Trail", page_icon="🏃", layout="wide")

# Nomes dos ficheiros CSV
FILE_MAIN = 'Provas_de_Equipa_2026_2027_Main.csv'
FILE_PROVAS = 'Provas_de_Equipa_2026_2027_Provas.csv'
FILE_INFO = 'Provas_de_Equipa_2026_2027_Info.csv'
FILE_HISTORICO = 'Provas_de_Equipa_2026_2027_Historico.csv'

# Função para carregar e limpar dados
COLS_PADRAO_MAIN = ['Prova', 'Atleta', 'Distância', 'Data', 'Local', 'Prova de Equipa', 'Link']

def load_csv(filename):
    if os.path.exists(filename):
        try:
            df = pd.read_csv(filename, sep=None, engine='python', encoding='utf-8-sig')
            df.columns = df.columns.astype(str).str.strip()

            # Se a primeira linha contiver os cabeçalhos verdadeiros (caso tenha havido desfasamento)
            if 'Unnamed: 3' in df.columns or 'Prova' not in df.columns:
                # Procura a linha que tem 'Prova' ou 'Atleta'
                for idx, row in df.iterrows():
                    if 'Prova' in row.values and 'Atleta' in row.values:
                        df.columns = [str(val).strip() for val in row.values]
                        df = df.iloc[idx + 1:].reset_index(drop=True)
                        break

            # Limpar colunas Unnamed e linhas vazias
            df = df.loc[:, ~df.columns.str.startswith('Unnamed')]
            df = df.dropna(how='all')

            # Se for o ficheiro Main ou Historico, garante apenas as 7 colunas certas na ordem exata
            if filename in [FILE_MAIN, FILE_HISTORICO]:
                for c in COLS_PADRAO_MAIN:
                    if c not in df.columns:
                        df[c] = ""
                df = df[COLS_PADRAO_MAIN]

            return df
        except Exception:
            pass
    return pd.DataFrame(columns=DEFAULT_COLS.get(filename, []))

def save_csv(df, filename):
    df.to_csv(filename, index=False)

# Carregamento dos dados
df_main = load_csv(FILE_MAIN)
df_provas = load_csv(FILE_PROVAS)
df_info = load_csv(FILE_INFO)
df_historico = load_csv(FILE_HISTORICO)

# --- SINCRONIZAÇÃO AUTOMÁTICA DE DATAS (MAIN -> HISTÓRICO) ---
def sync_expired_to_history(df_main, df_historico):
    if df_main.empty or 'Data' not in df_main.columns:
        return df_main, df_historico, 0

    today = date.today()
    parsed_dates = pd.to_datetime(df_main['Data'], errors='coerce').dt.date
    
    # Provas cuja data já passou
    expired_mask = parsed_dates < today
    expired_entries = df_main[expired_mask]

    if not expired_entries.empty:
        # Adicionar ao histórico e remover de Main
        df_historico = pd.concat([df_historico, expired_entries], ignore_index=True)
        df_main = df_main[~expired_mask].reset_index(drop=True)
        
        save_csv(df_main, FILE_MAIN)
        save_csv(df_historico, FILE_HISTORICO)
        return df_main, df_historico, len(expired_entries)
        
    return df_main, df_historico, 0

df_main, df_historico, moved_count = sync_expired_to_history(df_main, df_historico)

# Listas auxiliares a partir do Info.csv
atletas_list = sorted(df_info['Atleta'].dropna().astype(str).str.strip().unique().tolist())
distancias_list = sorted(df_info['Distancia'].dropna().astype(str).str.strip().unique().tolist())
provas_disponiveis = df_provas['PROVA'].dropna().unique().tolist() if not df_provas.empty else []

# --- INTERFACE GRÁFICA ---
st.title("🏃 Gestão de Provas de Equipa")

if moved_count > 0:
    st.info(f"ℹ️ {moved_count} prova(s) com data anterior a hoje foram transferidas para o Histórico.")

tab1, tab2, tab3 = st.tabs(["📅 Provas Agendadas (Main)", "📜 Histórico", "📋 Catálogo de Provas"])

# --- TAB 1: MAIN ---
with tab1:
    st.subheader("Inscrições Atuais da Equipa")

    col_filtro1, col_filtro2 = st.columns(2)
    with col_filtro1:
        filtro_atleta = st.selectbox("Filtrar por Atleta:", ["Todos"] + atletas_list, key="filtro_main_atleta")
    with col_filtro2:
        filtro_prova = st.selectbox("Filtrar por Prova:", ["Todas"] + sorted(df_main['Prova'].dropna().unique().tolist()) if not df_main.empty else ["Todas"], key="filtro_main_prova")

    df_view = df_main.copy()
    if filtro_atleta != "Todos":
        df_view = df_view[df_view['Atleta'] == filtro_atleta]
    if filtro_prova != "Todas":
        df_view = df_view[df_view['Prova'] == filtro_prova]

    st.dataframe(
        df_view,
        use_container_width=True,
        column_config={"Link": st.column_config.LinkColumn("Inscrição / Informações")}
    )

    st.markdown("---")
    st.subheader("➕ Registar Presença numa Prova")
    
    with st.form("form_add_prova_atleta", clear_on_submit=True):
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            atleta_sel = st.selectbox("Atleta:", atletas_list)
        with col_b:
            prova_sel = st.selectbox("Prova:", provas_disponiveis)
        with col_c:
            distancia_sel = st.selectbox("Tipo de Prova / Distância:", distancias_list if distancias_list else ["Geral"])

        # Obter dados da prova selecionada nos bastidores
        info_prova = df_provas[df_provas['PROVA'] == prova_sel]
        if not info_prova.empty:
            p_data = str(info_prova.iloc[0].get('DATA', ''))
            p_local = str(info_prova.iloc[0].get('LOCAL', ''))
            p_equipa = str(info_prova.iloc[0].get('PROVA DE EQUIPA', 'Não'))
            p_link = str(info_prova.iloc[0].get('Link', ''))
        else:
            p_data, p_local, p_equipa, p_link = "", "", "Não", ""

        submeter = st.form_submit_button("Confirmar Inscrição")

        if submeter:
            # Validação se a data da prova já expirou
            data_prova_dt = pd.to_datetime(p_data, errors='coerce').date()
            nova_linha = {
                'Prova': prova_sel,
                'Atleta': atleta_sel,
                'Distância': distancia_sel,
                'Data': p_data,
                'Local': p_local,
                'Prova de Equipa': p_equipa,
                'Link': p_link
            }

            if pd.notnull(data_prova_dt) and data_prova_dt < date.today():
                df_historico = pd.concat([df_historico, pd.DataFrame([nova_linha])], ignore_index=True)
                save_csv(df_historico, FILE_HISTORICO)
                st.warning("⚠️ Esta prova tem data passada, logo foi adicionada diretamente ao Histórico.")
            else:
                df_main = pd.concat([df_main, pd.DataFrame([nova_linha])], ignore_index=True)
                save_csv(df_main, FILE_MAIN)
                st.success(f"✅ Inscrição de {atleta_sel} na prova '{prova_sel}' guardada com sucesso!")
            st.rerun()

# --- TAB 2: HISTÓRICO ---
with tab2:
    st.subheader("Registo Histórico de Provas Concluídas")

    if not df_historico.empty:
        col_h1, col_h2 = st.columns(2)
        with col_h1:
            h_atleta = st.selectbox("Filtrar Histórico por Atleta:", ["Todos"] + atletas_list, key="hist_atleta")
        with col_h2:
            provas_hist = sorted(df_historico['Prova'].dropna().unique().tolist())
            h_prova = st.selectbox("Filtrar por Prova:", ["Todas"] + provas_hist, key="hist_prova")

        df_hist_view = df_historico.copy()
        if h_atleta != "Todos":
            df_hist_view = df_hist_view[df_hist_view['Atleta'] == h_atleta]
        if h_prova != "Todas":
            df_hist_view = df_hist_view[df_hist_view['Prova'] == h_prova]

        st.dataframe(
            df_hist_view,
            use_container_width=True,
            column_config={"Link": st.column_config.LinkColumn("Link")}
        )
    else:
        st.info("Nenhuma prova registada no histórico até ao momento.")

# --- TAB 3: CATÁLOGO DE PROVAS (PROVAS.CSV) ---
with tab3:
    st.subheader("Provas Oficiais Disponíveis no Calendário")
    st.dataframe(
        df_provas,
        use_container_width=True,
        column_config={"Link": st.column_config.LinkColumn("Link Oficial")}
    )

    st.markdown("---")
    st.subheader("➕ Adicionar Nova Prova ao Calendário Geral")
    with st.form("form_nova_prova_catalogo", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            n_nome = st.text_input("Nome da Prova:")
            n_data = st.date_input("Data da Prova:")
            n_local = st.text_input("Localidade:")
        with c2:
            n_equipa = st.selectbox("Conta como Prova de Equipa?", ["Não", "Sim"])
            n_link = st.text_input("Link da Inscrição / Organização:")

        submeter_prova = st.form_submit_button("Guardar Prova no Calendário")
        if submeter_prova:
            if n_nome.strip():
                nova_p = {
                    'PROVA': n_nome.strip(),
                    'DATA': n_data.strftime("%Y-%m-%d"),
                    'LOCAL': n_local.strip(),
                    'PROVA DE EQUIPA': n_equipa,
                    'Link': n_link.strip()
                }
                df_provas = pd.concat([df_provas, pd.DataFrame([nova_p])], ignore_index=True)
                save_csv(df_provas, FILE_PROVAS)
                st.success(f"Prova '{n_nome}' adicionada ao catálogo de provas!")
                st.rerun()
            else:
                st.error("O nome da prova é obrigatório.")
