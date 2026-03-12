import streamlit as st
import pandas as pd
import plotly.express as px

# Configuração da Página
st.set_page_config(page_title="Gestão de Performance Trimestral", layout="wide")

# Regra de Metas (Não alterada)
def calcular_nova_meta(row):
    if str(row['senioridade']).strip().capitalize() == 'Junior':
        tempo = row['tempo_empresa_meses']
        if tempo <= 1: return 3
        elif tempo == 2: return 4
        else: return 7
    return row['meta_news']

@st.cache_data
def load_and_process():
    df = pd.read_csv('supabase.csv')
    df['mes_referencia'] = pd.to_datetime(df['mes_referencia'])
    df['meta_news'] = df.apply(calcular_nova_meta, axis=1)
    df['Faltou Entrega'] = df['meta_news'] - df['news_realizados']
    df['% Atingido'] = (df['news_realizados'] / df['meta_news'] * 100).round(1)
    df['Ficou Abaixo'] = df['Faltou Entrega'] > 0
    return df

df_base = load_and_process()

# --- SIDEBAR (FILTROS) ---
st.sidebar.header("⚙️ Painel de Filtros")

meses_disponiveis = sorted(df_base['mes_referencia'].dt.strftime('%m/%Y').unique(), reverse=True)
meses_sel = st.sidebar.multiselect("Selecione os Meses", meses_disponiveis, default=meses_disponiveis)

hubs_sel = st.sidebar.multiselect("Unidades (Hubs)", sorted(df_base['hub'].unique()), default=sorted(df_base['hub'].unique()))

niveis_sel = st.sidebar.multiselect("Nível do Promotor", sorted(df_base['senioridade'].unique()), default=sorted(df_base['senioridade'].unique()))

tempo_casa = st.sidebar.slider("Tempo de Casa (Meses)", 0, 24, (0, 24))

# Aplicação dos filtros
df_filtrado = df_base[
    (df_base['mes_referencia'].dt.strftime('%m/%Y').isin(meses_sel)) &
    (df_base['hub'].isin(hubs_sel)) &
    (df_base['senioridade'].isin(niveis_sel)) &
    (df_base['tempo_empresa_meses'].between(tempo_casa[0], tempo_casa[1]))
].copy()

# --- TÍTULO ---
st.title("🎯 Gestão de Resultados: Quem não bateu a meta?")
st.markdown("Passe o mouse sobre os gráficos para ver detalhes de cada promotor ou unidade.")

# --- ABAS ---
tab_agora, tab_acumulado = st.tabs(["📌 Situação Mensal", "⚠️ Histórico e Recorrência"])

# ---------------------------------------------------------
# TAB 1: SITUAÇÃO MENSAL
# ---------------------------------------------------------
with tab_agora:
    if len(meses_sel) > 0:
        mes_foco = st.selectbox("Ver detalhes do mês:", meses_sel)
        df_m = df_filtrado[(df_filtrado['mes_referencia'].dt.strftime('%m/%Y') == mes_foco) & (df_filtrado['Ficou Abaixo'])].copy()

        # KPIs Diretos
        k1, k2, k3 = st.columns(3)
        k1.metric("Pessoas Fora da Meta", len(df_m))
        k2.metric("Total NÃO entregue", f"{int(df_m['Faltou Entrega'].sum())} Un")
        k3.metric("Média de Entrega", f"{df_m['% Atingido'].mean():.1f}%" if not df_m.empty else "0%")

        st.divider()

        # Gráfico de Barras com HOVER detalhado
        df_h = df_m.groupby(['hub', 'senioridade']).agg({'Faltou Entrega': 'sum'}).reset_index().sort_values('Faltou Entrega', ascending=False)
        fig_h = px.bar(df_h, x='hub', y='Faltou Entrega', color='senioridade',
                       title="Volume Faltante por Unidade e Nível",
                       hover_data={'hub': True, 'senioridade': True, 'Faltou Entrega': True})
        st.plotly_chart(fig_h, use_container_width=True)

        st.subheader(f"Lista de Chamada - {mes_foco}")
        st.dataframe(
            df_m[['nome_promotor', 'hub', 'senioridade', 'tempo_empresa_meses', 'meta_news', 'news_realizados', 'Faltou Entrega', '% Atingido']].sort_values('Faltou Entrega', ascending=False),
            column_config={
                "nome_promotor": "Nome", "hub": "Unidade", "senioridade": "Nível",
                "tempo_empresa_meses": "Meses Casa", "meta_news": "Meta",
                "news_realizados": "Fez", "Faltou Entrega": "Faltou",
                "% Atingido": st.column_config.ProgressColumn("Atingimento", format="%.0f%%", min_value=0, max_value=100)
            },
            hide_index=True, use_container_width=True
        )
    else:
        st.error("Selecione um mês na barra lateral.")

# ---------------------------------------------------------
# TAB 2: HISTÓRICO E RECORRÊNCIA
# ---------------------------------------------------------
with tab_acumulado:
    st.subheader("Ranking de Recorrência (Últimos Meses)")
    
    df_rec = df_filtrado[df_filtrado['Ficou Abaixo']].groupby(['nome_promotor', 'hub', 'senioridade']).agg({
        'mes_referencia': 'count',
        'Faltou Entrega': 'sum',
        'news_realizados': 'sum',
        'tempo_empresa_meses': 'max'
    }).reset_index()
    
    df_rec.columns = ['Nome', 'Unidade', 'Nível', 'Meses sem bater Meta', 'Dívida Acumulada', 'Total Realizado', 'Tempo Casa']

    st.write("---")
    f1, f2 = st.columns([1, 2])
    with f1:
        alerta = st.radio("Grau de Alerta:", ["Todos", "Críticos (3 meses fora)", "Atenção (2 meses fora)"])
        if "Críticos" in alerta: df_rec = df_rec[df_rec['Meses sem bater Meta'] >= 3]
        elif "Atenção" in alerta: df_rec = df_rec[df_rec['Meses sem bater Meta'] == 2]

    with f2:
        # Gráfico de Barras Horizontal dos Top 10 Piores com HOVER completo
        df_top10 = df_rec.sort_values('Dívida Acumulada', ascending=False).head(10)
        fig_top = px.bar(df_top10, x='Dívida Acumulada', y='Nome', orientation='h',
                         color='Meses sem bater Meta',
                         title="Top 10: Maiores Devedores de News",
                         hover_data=['Unidade', 'Nível', 'Tempo Casa', 'Meses sem bater Meta'],
                         color_continuous_scale='Reds')
        st.plotly_chart(fig_top, use_container_width=True)

    st.subheader("Relatório de Reincidência (Ranking Prioritário)")
    st.dataframe(
        df_rec.sort_values(['Meses sem bater Meta', 'Dívida Acumulada'], ascending=False),
        column_config={
            "Meses sem bater Meta": st.column_config.NumberColumn("Meses de Falha", format="%d ⚠️"),
            "Dívida Acumulada": "Total que Faltou",
            "Tempo Casa": "Meses na Empresa"
        },
        hide_index=True, use_container_width=True
    )

st.info("💡 **Dica de Gestão:** Ao passar o mouse no gráfico de barras, você descobre a Unidade e o Tempo de Casa do promotor sem precisar procurar na tabela.")