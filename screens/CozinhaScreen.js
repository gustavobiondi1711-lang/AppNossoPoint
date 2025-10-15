import React from 'react';
import {
  View,
  FlatList,
  Text,
  StyleSheet,
  Button,
  RefreshControl,
  TouchableOpacity,
} from 'react-native';
import { UserContext } from '../UserContext';
import { getSocket } from '../socket';

// =============== Helpers ===============
const formatBRL = (n) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
    .format(Number(n || 0));

const safeParseOptions = (raw) => {
  if (!raw) return [];
  try {
    return Array.isArray(raw) ? raw : JSON.parse(raw);
  } catch (_e) {
    try {
      return JSON.parse(String(raw).replace(/'/g, '"'));
    } catch {
      return [];
    }
  }
};

/** Exibe grupos/opções selecionadas/ativas (sem valor_extra) */
const formatSelectedOptions = (rawOpcoes) => {
  const groups = safeParseOptions(rawOpcoes);
  if (!Array.isArray(groups) || groups.length === 0) return '';

  const lines = [];
  for (const g of groups) {
    const all = (g?.options || g?.opcoes || []);
    const opts = all.filter(
      (o) => o?.selecionado === true || typeof o?.selecionado === 'undefined'
    );
    if (opts.length === 0) continue;

    const optsTxt = opts.map((o) => o?.nome).join(', ');
    const groupName = g?.nome || 'Opções';
    lines.push(`${groupName}: ${optsTxt}`);
  }
  return lines.join(' | ');
};

const formatHoraCurta = (s) => {
  if (!s) return '';
  const m = String(s).match(/^(\d{2}:\d{2})(:\d{2})?$/);
  return m ? m[1] : s;
};

const estadoStyle = (estado) => {
  switch ((estado || '').toLowerCase()) {
    case 'em preparo':
      return { bg: '#FFF3E0', fg: '#EF6C00' }; // laranja suave
    case 'pronto':
      return { bg: '#E8F5E9', fg: '#2E7D32' }; // verde suave
    default:
      return { bg: '#E3F2FD', fg: '#1565C0' }; // azul suave
  }
};
// =======================================

export default class Cozinha extends React.Component {
  static contextType = UserContext;

  constructor(props) {
    super(props);
    this.state = {
      data: [],
      data_filtrado: [],
      showFiltrado: false,
      refreshing: false,
    };
    this.refreshData = this.refreshData.bind(this);
    this.socket = null;
    this.refreshTimeout = null;
  }

  componentDidMount() {
    this.socket = getSocket();
    this.socket.on('respostaPedidos', this.handleRespostaPedidos);
    this.refreshData();
  }

  componentWillUnmount() {
    if (this.socket) {
      this.socket.off('respostaPedidos', this.handleRespostaPedidos);
    }
    if (this.refreshTimeout) clearTimeout(this.refreshTimeout);
  }

  handleRespostaPedidos = (dados) => {
    if (!dados?.dataPedidos) {
      this.setState({ refreshing: false });
      return;
    }
    const data_temp = dados.dataPedidos.filter((item) => item.categoria === '3');
    const data_temp_filtrado = data_temp.filter((item) => item.estado !== 'Pronto');

    this.setState({
      data: data_temp,
      data_filtrado: data_temp_filtrado,
      refreshing: false,
    });
  };

  refreshData = () => {
    this.setState({ refreshing: true }, () => {
      this.socket.emit('getPedidos', false);
      if (this.refreshTimeout) clearTimeout(this.refreshTimeout);
      this.refreshTimeout = setTimeout(() => {
        this.setState({ refreshing: false });
      }, 5000);
    });
  };

  alterar_estado(id, estado) {
    this.socket.emit('inserir_preparo', { id, estado });
  }

  filtrar = () => {
    this.setState((prev) => ({ showFiltrado: !prev.showFiltrado }));
  };

  renderItem = ({ item }) => {
    const optionsText = formatSelectedOptions(item?.opcoes);
    const { bg, fg } = estadoStyle(item?.estado);

    // extras do banco
    const remetente = item?.remetente;
    const comanda = item?.comanda;
    const endereco = item?.endereco_entrega;
    const horaEntrega = item?.horario_para_entrega;

    // Chip: mostra Remetente e, dentro, a Comanda
    const remHeader =
      remetente || comanda
        ? `${remetente ? remetente : ''}${
            comanda ? `${remetente ? ' · ' : ''}Comanda ${comanda}` : ''
          }`
        : '';

    return (
      <View style={styles.card}>
        {/* Cabeçalho do card (Remetente + Estado) */}
        <View style={styles.cardHeader}>
          {!!remHeader && (
            <View style={styles.pillRemetente}>
              <Text style={styles.pillRemetenteText}>{remHeader}</Text>
            </View>
          )}
          <View style={[styles.pillEstado, { backgroundColor: bg }]}>
            <Text style={[styles.pillEstadoText, { color: fg }]}>
              {item?.estado || 'A Fazer'}
            </Text>
          </View>
        </View>

        {/* Pedido */}
        <Text style={styles.pedidoTitle}>{item?.pedido}</Text>

        {!!optionsText && <Text style={styles.optionsText}>{optionsText}</Text>}
        {!!item?.extra && <Text style={styles.extraText}>Obs: {item.extra}</Text>}

        {/* Entrega (se houver) */}
        {(endereco || horaEntrega) && (
          <View style={styles.deliveryBox}>
            {!!endereco && (
              <Text style={styles.deliveryLine}>
                <Text style={styles.deliveryLabel}>Entrega: </Text>
                {endereco}
              </Text>
            )}
            {!!horaEntrega && (
              <Text style={styles.deliveryLine}>
                <Text style={styles.deliveryLabel}>Prazo: </Text>
                {formatHoraCurta(horaEntrega)}
              </Text>
            )}
          </View>
        )}

        {/* Ações */}
        <View style={styles.actionsRow}>
          {item.estado === 'Em Preparo' ? (
            <Button
              color="orange"
              title="Pronto"
              onPress={() => this.alterar_estado(item.id, 'Pronto')}
            />
          ) : item.estado === 'A Fazer' ? (
            <Button
              color="blue"
              title="Começar"
              onPress={() => this.alterar_estado(item.id, 'Em Preparo')}
            />
          ) : (
            <Button
              color="green"
              title="Desfazer"
              onPress={() => this.alterar_estado(item.id, 'A Fazer')}
            />
          )}
        </View>
      </View>
    );
  };

  render() {
    const { showFiltrado, refreshing, data, data_filtrado } = this.state;
    const dataToShow = showFiltrado ? data : data_filtrado;

    return (
      <View style={styles.container}>
        {/* sem header; apenas o toggle */}
        <View style={styles.topActions}>
          <TouchableOpacity onPress={this.filtrar} style={styles.toggleBtn}>
            <Text style={styles.toggleBtnText}>
              {showFiltrado ? 'Filtrar' : 'Todos'}
            </Text>
          </TouchableOpacity>
        </View>

        <FlatList
          data={dataToShow}
          keyExtractor={(item, index) => String(item?.id ?? index)}
          renderItem={this.renderItem}
          contentContainerStyle={styles.listContent}
          ItemSeparatorComponent={() => <View style={{ height: 10 }} />}
          ListEmptyComponent={
            !refreshing ? (
              <Text style={styles.emptyText}>Nenhum pedido por aqui…</Text>
            ) : null
          }
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={this.refreshData} />
          }
        />
      </View>
    );
  }
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 10, backgroundColor: '#F7F9F8' },

  topActions: { alignItems: 'flex-end', marginBottom: 8 },
  toggleBtn: {
    backgroundColor: '#E3F2FD',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 16,
  },
  toggleBtnText: { color: '#1565C0', fontWeight: '600' },

  listContent: { paddingBottom: 16 },

  card: {
    backgroundColor: '#FFF',
    borderRadius: 14,
    padding: 12,
    shadowColor: '#000',
    shadowOpacity: 0.08,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
    elevation: 3,
  },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 6 },

  pillRemetente: {
    backgroundColor: '#E8F5E9', // verde claro
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 4,
    maxWidth: '75%',
  },
  pillRemetenteText: { color: '#2E7D32', fontWeight: '700', fontSize: 12 },

  pillEstado: { borderRadius: 12, paddingHorizontal: 10, paddingVertical: 4 },
  pillEstadoText: { fontWeight: '700', fontSize: 12 },

  pedidoTitle: { fontSize: 18, fontWeight: '700', color: '#222', marginTop: 2 },
  optionsText: { marginTop: 6, fontSize: 14, color: '#444' },
  extraText: { marginTop: 4, fontSize: 13, color: '#666', fontStyle: 'italic' },

  deliveryBox: { marginTop: 8, backgroundColor: '#F5F5F5', borderRadius: 10, padding: 8 },
  deliveryLine: { fontSize: 13, color: '#333', marginBottom: 2 },
  deliveryLabel: { fontWeight: '700', color: '#222' },

  actionsRow: { marginTop: 10, alignItems: 'flex-end' },

  emptyText: { textAlign: 'center', marginTop: 24, color: '#777' },
});
