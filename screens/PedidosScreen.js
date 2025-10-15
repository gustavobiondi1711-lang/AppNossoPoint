import React from 'react';
import {
  View,
  FlatList,
  Text,
  StyleSheet,
  TextInput,
  Modal,
  TouchableOpacity,
  RefreshControl,
  ScrollView,
  Alert,
  Platform,
} from 'react-native';
import { UserContext } from '../UserContext';
import { getSocket } from '../socket';

// Util para normalizar e facilitar buscas ignorando acentos/maiúsculas
const normalize = (s) =>
  String(s || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();

// convierte algo para número seguro
const toInt = (v, d = 0) => {
  const n = parseInt(String(v).replace(/[^0-9-]/g, ''), 10);
  return Number.isFinite(n) ? n : d;
};
const toFloat = (v, d = 0) => {
  const n = parseFloat(String(v).replace(',', '.').replace(/[^0-9.\-]/g, ''));
  return Number.isFinite(n) ? n : d;
};

// valida HH:MM
const isHHMM = (s) => /^([01]\d|2[0-3]):([0-5]\d)$/.test(String(s || '').trim());

export default class PedidosScreen extends React.Component {
  static contextType = UserContext;

  constructor(props) {
    super(props);
    this.state = {
      // dados
      data: [],
      refreshing: false,

      // filtros
      filtroComanda: '',
      filtroItem: '',
      filtroCategoria: null, // null = todas; '1' = apenas categoria 1; etc.
      categoriasDisponiveis: [],

      // modal
      showModal: false,
      editable: false,
      pedidoModal: {},

      // UI
      carregandoConfirmar: false,
    };
    this.socket = null;
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
    if (this._refreshTimeout) clearTimeout(this._refreshTimeout);
  }

  // ---------- socket handlers ----------
  handleRespostaPedidos = (dados) => {
    const arr = Array.isArray(dados?.dataPedidos) ? [...dados.dataPedidos].reverse() : [];
    const categorias = Array.from(
      new Set(arr.map((i) => String(i?.categoria ?? '')).filter((c) => c && c !== 'null' && c !== 'undefined'))
    );
    this.setState({ data: arr, categoriasDisponiveis: categorias, refreshing: false });
  };

  refreshData = () => {
    this.setState({ refreshing: true }, () => {
      this.socket.emit('getPedidos', false);
      if (this._refreshTimeout) clearTimeout(this._refreshTimeout);
      this._refreshTimeout = setTimeout(() => this.setState({ refreshing: false }), 10000);
    });
  };

  // ---------- filtros ----------
  getFilteredData = () => {
    const { data, filtroComanda, filtroItem, filtroCategoria } = this.state;
    const nCom = normalize(filtroComanda);
    const nItem = normalize(filtroItem);

    return (data || []).filter((it) => {
      const okComanda = nCom ? normalize(it?.comanda).includes(nCom) : true;
      const okItem = nItem ? normalize(it?.pedido).includes(nItem) : true;
      const okCat = filtroCategoria ? String(it?.categoria) === String(filtroCategoria) : true;
      return okComanda && okItem && okCat;
    });
  };

  limparFiltros = () => {
    this.setState({ filtroComanda: '', filtroItem: '', filtroCategoria: null });
  };

  // ---------- modal ----------
  abrirModal = (item) => {
    // protege campos ausentes
    const safe = {
      id: item?.id ?? null,
      comanda: item?.comanda ?? '',
      pedido: item?.pedido ?? '',
      quantidade: String(item?.quantidade ?? ''),
      preco: String(item?.preco ?? ''),
      inicio: item?.inicio ?? '',
      fim: item?.fim ?? '',
      comecar: item?.comecar ?? '',
      estado: item?.estado ?? '',
      extra: item?.extra ?? '',
      username: item?.username ?? '',
      ordem: item?.ordem ?? '',
      nome: item?.nome ?? '',
      dia: item?.dia ?? '',
      orderTiming: item?.orderTiming ?? '',
      endereco_entrega: item?.endereco_entrega ?? '',
      order_id: item?.order_id ?? '',
      remetente: item?.remetente ?? '',
      horario_para_entrega: item?.horario_para_entrega ?? '',
      categoria: item?.categoria ?? '',
      preco_unitario: String(item?.preco_unitario ?? ''),
      opcoes: item?.opcoes ?? '', // string JSON ou texto
      quantidade_paga: String(item?.quantidade_paga ?? '0'),
      printed: item?.printed ?? 0,
    };

    this.setState({ pedidoModal: safe, showModal: true, editable: false });
  };

  fecharModal = () => {
    this.setState({ showModal: false, editable: false, pedidoModal: {} });
  };

  entrarEdicao = () => this.setState({ editable: true });
  sairEdicao = () => this.setState({ editable: false });

  onChangeCampo = (campo, valor) => {
    this.setState((prev) => {
      const novo = { ...prev.pedidoModal, [campo]: valor };

      // automatizações
      if (campo === 'quantidade') {
        const q = Math.max(0, toInt(valor, 0));
        const pu = toFloat(novo.preco_unitario, 0);
        // atualiza preco com base em PU * Q
        novo.preco = String((pu * q).toFixed(2));
        // ajusta quantidade_paga para não exceder a nova quantidade
        const qpAntigo = toInt(prev.pedidoModal.quantidade_paga, 0);
        novo.quantidade_paga = String(Math.min(q, Math.max(0, qpAntigo)));
      }

      if (campo === 'preco_unitario') {
        const pu = toFloat(valor, 0);
        const q = Math.max(0, toInt(novo.quantidade, 0));
        novo.preco = String((pu * q).toFixed(2));
      }

      return { pedidoModal: novo };
    });
  };

  salvarEdicao = () => {
    const { user } = this.context || {};
    const p = this.state.pedidoModal;

    // validações básicas
    const q = toInt(p.quantidade, NaN);
    if (!Number.isFinite(q)) {
      Alert.alert('Erro', 'Quantidade inválida (somente números).');
      return;
    }
    const qp = toInt(p.quantidade_paga, NaN);
    if (!Number.isFinite(qp)) {
      Alert.alert('Erro', 'Quantidade paga inválida (somente números).');
      return;
    }
    if (qp > q) {
      Alert.alert('Erro', 'Quantidade paga não pode ser maior que a quantidade.');
      return;
    }

    const pu = toFloat(p.preco_unitario, NaN);
    if (!Number.isFinite(pu)) {
      Alert.alert('Erro', 'Preço unitário inválido.');
      return;
    }

    const preco = toFloat(p.preco, NaN);
    if (!Number.isFinite(preco)) {
      Alert.alert('Erro', 'Preço inválido.');
      return;
    }

    const h = String(p.horario_para_entrega || '').trim();
    if (h && !isHHMM(h)) {
      Alert.alert('Erro', 'Horário para entrega deve estar no formato HH:MM.');
      return;
    }

    // monta payload apenas com campos permitidos para edição
    const payload = {
      id: p.id, // se existir
      comanda: p.comanda,
      preco: String(preco),
      quantidade: String(q),
      quantidade_paga: String(qp),
      preco_unitario: String(pu),
      opcoes: p.opcoes ?? '',
      extra: p.extra ?? '',
      horario_para_entrega: h, // pode ser vazio
    };

    try {
      this.socket.emit('atualizar_pedidos', {
        pedidoAlterado: payload,
        usuario: user?.username,
        token: user?.token,
      });
      this.setState({ editable: false, showModal: false, pedidoModal: {} });
    } catch (e) {
      Alert.alert('Erro', 'Não foi possível salvar a edição agora.');
    }
  };

  // confirmar (marcar printed=1) — aparece só no filtro categoria "1" e quando printed == 0
  confirmarPedido = async (item) => {
    const { user } = this.context || {};
    if (!item?.id) return;

    try {
      this.setState({ carregandoConfirmar: true });
      const payload = {
        id: item.id,
        printed: 1,
      };
      this.socket.emit('atualizar_pedidos', {
        pedidoAlterado: payload,
        usuario: user?.username,
        token: user?.token,
      });
    } catch (e) {
      Alert.alert('Erro', 'Não foi possível confirmar o pedido.');
    } finally {
      this.setState({ carregandoConfirmar: false });
    }
  };

  // ---------- render ----------
  renderHeaderFiltros() {
    const { filtroComanda, filtroItem, filtroCategoria, categoriasDisponiveis } = this.state;

    return (
      <View style={styles.filtersContainer}>
        <View style={styles.filtersRow}>
          <TextInput
            placeholder="Filtrar por comanda"
            placeholderTextColor="#999"
            value={filtroComanda}
            onChangeText={(v) => this.setState({ filtroComanda: v })}
            style={styles.filterInput}
            autoCorrect={false}
            autoCapitalize="none"
          />
          <TextInput
            placeholder="Filtrar por item"
            placeholderTextColor="#999"
            value={filtroItem}
            onChangeText={(v) => this.setState({ filtroItem: v })}
            style={styles.filterInput}
            autoCorrect={false}
            autoCapitalize="none"
          />
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 8 }}>
          <TouchableOpacity
            style={[styles.catChip, !filtroCategoria && styles.catChipActive]}
            onPress={() => this.setState({ filtroCategoria: null })}
          >
            <Text style={[styles.catChipText, !filtroCategoria && styles.catChipTextActive]}>Todas</Text>
          </TouchableOpacity>

          {categoriasDisponiveis.map((c) => {
            const isActive = String(filtroCategoria) === String(c);
            return (
              <TouchableOpacity
                key={c}
                style={[styles.catChip, isActive && styles.catChipActive]}
                onPress={() => this.setState({ filtroCategoria: c })}
              >
                <Text style={[styles.catChipText, isActive && styles.catChipTextActive]}>
                  Categoria {String(c)}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>

        <View style={styles.filtersActions}>
          <TouchableOpacity style={[styles.btn, styles.btnGray]} onPress={this.limparFiltros}>
            <Text style={styles.btnText}>Limpar filtros</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.btn, styles.btnPrimary]} onPress={this.refreshData}>
            <Text style={styles.btnText}>Atualizar</Text>
          </TouchableOpacity>
        </View>

        {String(filtroCategoria) === '1' && (
          <Text style={styles.note}>
            Dica: no filtro Categoria 1, o botão “Confirmar” aparece apenas quando <Text style={{ fontWeight: '800' }}>printed = 0</Text>.
          </Text>
        )}
      </View>
    );
  }

  renderItemRow = ({ item }) => {
    const { filtroCategoria } = this.state;
    const printed = Number(item?.printed || 0);
    const showConfirm =
      String(filtroCategoria) === '1' && printed === 0;

    return (
      <View style={styles.card}>
        <TouchableOpacity onPress={() => this.abrirModal(item)} activeOpacity={0.8} style={{ flex: 1 }}>
          <Text style={styles.cardTitle}>
            {item?.quantidade}× {item?.pedido} {item?.extra ? `(${item.extra})` : '' }
          </Text>
          <Text style={styles.cardMeta}>
            Comanda: <Text style={styles.cardMetaStrong}>{item?.comanda}</Text> • Início: {item?.inicio || '—'}
          </Text>
          <Text style={styles.cardMeta}>
            Categoria: {String(item?.categoria ?? '—')} • Printed: {printed}
          </Text>
          {!!item?.preco && (
            <Text style={styles.cardMeta}>
              Preço: {item?.preco} {item?.preco_unitario ? ` • PU: ${item.preco_unitario}` : ''}
            </Text>
          )}
        </TouchableOpacity>

        {showConfirm && (
          <TouchableOpacity
            style={[styles.btn, styles.btnConfirm]}
            onPress={() => this.confirmarPedido(item)}
            disabled={this.state.carregandoConfirmar}
          >
            <Text style={styles.btnText}>
              {this.state.carregandoConfirmar ? '...' : 'Confirmar'}
            </Text>
          </TouchableOpacity>
        )}
      </View>
    );
  };

  renderModal() {
    const { showModal, editable, pedidoModal } = this.state;
    if (!showModal) return null;

    const field = (label, value, editableNow, onChange, extraProps = {}) => (
      <View style={styles.modalRow}>
        <Text style={styles.modalLabel}>{label}</Text>
        <TextInput
          style={[styles.modalInput, !editableNow && styles.modalInputReadonly]}
          value={String(value ?? '')}
          editable={!!editableNow}
          onChangeText={onChange}
          placeholderTextColor="#999"
          {...extraProps}
        />
      </View>
    );

    return (
      <Modal
        animationType="slide"
        transparent
        visible={showModal}
        onRequestClose={this.fecharModal}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <ScrollView style={{ maxHeight: Platform.OS === 'ios' ? 520 : 560 }}>
              <Text style={styles.modalTitle}>Detalhes do Pedido</Text>

              {/* Campos somente visualização */}
              {field('ID', pedidoModal.id, false)}
              {field('Pedido', pedidoModal.pedido, false)}
              {field('Usuário', pedidoModal.username, false)}
              {field('Nome', pedidoModal.nome, false)}
              {field('Estado', pedidoModal.estado, false)}
              {field('Início', pedidoModal.inicio, false)}
              {field('Fim', pedidoModal.fim, false)}
              {field('Começar', pedidoModal.comecar, false)}
              {field('Dia', pedidoModal.dia, false)}
              {field('Ordem', pedidoModal.ordem, false)}
              {field('OrderTiming', pedidoModal.orderTiming, false)}
              {field('Endereço Entrega', pedidoModal.endereco_entrega, false)}
              {field('Order ID', pedidoModal.order_id, false)}
              {field('Remetente', pedidoModal.remetente, false)}
              {field('Categoria', pedidoModal.categoria, false)}
              {field('Printed', pedidoModal.printed, false)}

              {/* Campos editáveis (exigidos) */}
              {field(
                'Comanda',
                pedidoModal.comanda,
                editable,
                (v) => this.onChangeCampo('comanda', v)
              )}

              {field(
                'Quantidade',
                pedidoModal.quantidade,
                editable,
                (v) => this.onChangeCampo('quantidade', v),
                { keyboardType: 'numeric' }
              )}

              {field(
                'Quantidade Paga',
                pedidoModal.quantidade_paga,
                editable,
                (v) => this.onChangeCampo('quantidade_paga', v),
                { keyboardType: 'numeric' }
              )}

              {field(
                'Preço Unitário',
                pedidoModal.preco_unitario,
                editable,
                (v) => this.onChangeCampo('preco_unitario', v),
                { keyboardType: 'numeric' }
              )}

              {field(
                'Preço',
                pedidoModal.preco,
                editable,
                (v) => this.onChangeCampo('preco', v),
                { keyboardType: 'numeric' }
              )}

              {field(
                'Opções (texto/JSON)',
                pedidoModal.opcoes,
                editable,
                (v) => this.onChangeCampo('opcoes', v),
                { multiline: true }
              )}

              {field(
                'Extra',
                pedidoModal.extra,
                editable,
                (v) => this.onChangeCampo('extra', v)
              )}

              {field(
                'Horário p/ Entrega (HH:MM)',
                pedidoModal.horario_para_entrega,
                editable,
                (v) => this.onChangeCampo('horario_para_entrega', v),
                { keyboardType: 'numbers-and-punctuation' }
              )}
            </ScrollView>

            <View style={styles.modalActions}>
              <TouchableOpacity style={[styles.btn, styles.btnGray]} onPress={this.fecharModal}>
                <Text style={styles.btnText}>Fechar</Text>
              </TouchableOpacity>

              {editable ? (
                <>
                  <TouchableOpacity style={[styles.btn, styles.btnOutline]} onPress={this.sairEdicao}>
                    <Text style={styles.btnOutlineText}>Cancelar</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={[styles.btn, styles.btnPrimary]} onPress={this.salvarEdicao}>
                    <Text style={styles.btnText}>Salvar</Text>
                  </TouchableOpacity>
                </>
              ) : (
                <TouchableOpacity style={[styles.btn, styles.btnPrimary]} onPress={this.entrarEdicao}>
                  <Text style={styles.btnText}>Editar</Text>
                </TouchableOpacity>
              )}
            </View>
          </View>
        </View>
      </Modal>
    );
  }

  render() {
    const { refreshing } = this.state;
    const data = this.getFilteredData();

    return (
      <View style={styles.container}>
        {this.renderHeaderFiltros()}

        <FlatList
          data={data}
          keyExtractor={(item, index) => String(item?.id ?? index)}
          renderItem={this.renderItemRow}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={this.refreshData} />
          }
          ListEmptyComponent={
            <View style={{ paddingVertical: 24, alignItems: 'center' }}>
              <Text style={{ color: '#6b7280' }}>Sem pedidos para exibir.</Text>
            </View>
          }
          contentContainerStyle={{ paddingBottom: 16 }}
        />

        {this.renderModal()}
      </View>
    );
  }
}

// ---------- styles ----------
const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },

  // filtros
  filtersContainer: { paddingHorizontal: 12, paddingTop: 12, paddingBottom: 8, backgroundColor: '#f8fafc' },
  filtersRow: { flexDirection: 'row', gap: 8 },
  filterInput: {
    flex: 1,
    height: 42,
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 10,
    paddingHorizontal: 10,
    backgroundColor: '#fff',
  },
  filtersActions: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 8 },
  btn: {
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: 120,
  },
  btnPrimary: { backgroundColor: '#17315c' },
  btnConfirm: { backgroundColor: '#059669', marginTop: 8, alignSelf: 'flex-start' },
  btnGray: { backgroundColor: '#e5e7eb' },
  btnText: { color: '#fff', fontWeight: '800' },
  btnOutline: { backgroundColor: '#fff', borderWidth: 1, borderColor: '#9ca3af' },
  btnOutlineText: { color: '#111827', fontWeight: '800' },
  note: { marginTop: 8, color: '#6b7280', fontSize: 12 },

  // categorias
  catChip: {
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: '#d1d5db',
    backgroundColor: '#fff',
    marginRight: 8,
  },
  catChipActive: { backgroundColor: '#17315c', borderColor: '#17315c' },
  catChipText: { color: '#374151', fontWeight: '700' },
  catChipTextActive: { color: '#fff', fontWeight: '800' },

  // cards
  card: {
    marginHorizontal: 12,
    marginTop: 10,
    padding: 14,
    borderRadius: 12,
    backgroundColor: '#f9fafb',
    borderWidth: 1,
    borderColor: '#e5e7eb',
  },
  cardTitle: { fontSize: 16, fontWeight: '800', color: '#111827' },
  cardMeta: { marginTop: 4, color: '#374151' },
  cardMetaStrong: { fontWeight: '800', color: '#111827' },

  // modal
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.45)',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 12,
  },
  modalContent: {
    width: '100%',
    maxWidth: 520,
    backgroundColor: '#fff',
    borderRadius: 14,
    padding: 16,
  },
  modalTitle: { fontSize: 18, fontWeight: '800', color: '#111827', textAlign: 'center', marginBottom: 8 },
  modalRow: { marginTop: 8 },
  modalLabel: { fontWeight: '700', color: '#374151', marginBottom: 4 },
  modalInput: {
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 10,
    backgroundColor: '#fff',
  },
  modalInputReadonly: { backgroundColor: '#f3f4f6' },
  modalActions: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 12, gap: 10 },
});
