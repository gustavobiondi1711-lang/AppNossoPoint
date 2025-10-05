import React from 'react';
import {
  View,
  FlatList,
  Text,
  StyleSheet,
  TouchableOpacity,
  RefreshControl,
  Modal,
  StatusBar,
} from 'react-native';
import { API_URL } from "./url";
import { UserContext } from '../UserContext';
import { PrinterService } from '../PrinterService';
import { getSocket } from '../socket';

const COLORS = {
  bg: '#FFFFFF',
  text: '#0A0A0A',
  muted: '#444',
  border: '#000',
  card: '#FFFFFF',

  // filtro (volta o antigo)
  chipOn: '#111',
  chipOff: '#E0E0E0',
  chipTextOn: '#FFD600',

  // ações
  primary: '#1565C0',   // COMEÇAR
  success: '#2E7D32',   // TERMINAR
  danger:  '#C62828',   // DESFAZER
};

export default class BarmanScreen extends React.Component {
  static contextType = UserContext

  constructor(props) {
    super(props);
    this.state = {
      data: [],
      data_filtrado: [],
      showFiltrado: true,
      ingredientes: [],
      refreshing:false,
      showModal:false,
    };
    this.socket = null;
    this.refreshData = this.refreshData.bind(this);
    this.alterar_estado = this.alterar_estado.bind(this);
    this.filtrar = this.filtrar.bind(this);
    this.extra = this.extra.bind(this);
  }

  componentDidMount() {
    const { user } = this.context || {};
    this.socket = getSocket();
    this.socket.emit("getPedidos", false);
    this.socket.on("respostaPedidos", this.handleRespostaPedidos);
    this.socket.on("ingrediente", this.handleIngrediente);

    if (user?.username === "gustavobiondi") {
      this.processPendingPrintOrders();
      this.socket.on("emitir_pedido_restante", this.handleEmitirPedidoRestante);
    }
  }

  componentWillUnmount() {
    if (this.socket) {
      this.socket.off("respostaPedidos", this.handleRespostaPedidos);
      this.socket.off("ingrediente", this.handleIngrediente);
      this.socket.off("emitir_pedido_restante", this.handleEmitirPedidoRestante);
    }
  }

  // ---------- handlers ----------
  handleRespostaPedidos = (dados) => {
    if (!dados?.dataPedidos) return;

    const data_temp = dados.dataPedidos.filter((item) => item.categoria === "2");
    const data_temp_filtrado = data_temp.filter((item) => item.estado !== "Pronto");

    this.setState({
      data: data_temp,
      data_filtrado: data_temp_filtrado,
    });
  };

  handleIngrediente = ({ data }) => {
    this.setState({ ingredientes: data });
  };

  handleEmitirPedidoRestante = async (data) => {
    try {
      await PrinterService.printPedido({
        mesa: data.mesa,
        pedido: data.pedido,
        quant: data.quantidade,
        extra: data.extra,
        hora: data.hora,
        sendBy: data.sendBy,
      });

      await fetch(`${API_URL}/updatePrinted`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pedidoId: data.id }),
      });
    } catch (e) {
      console.log("Erro ao imprimir:", e);
    }
  };

  // ---------- fluxo inicial de impressões pendentes ----------
  processPendingPrintOrders = async () => {
    try {
      const resp = await fetch(`${API_URL}/getPendingPrintOrders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ printed: 0, ordem: 0 }),
      });

      const text = await resp.text();
      if (!resp.ok) throw new Error(`HTTP ${resp.status} ${resp.statusText} :: ${text}`);

      let data;
      try { data = JSON.parse(text); }
      catch { throw new Error(`Resposta não-JSON do servidor: ${text.slice(0, 300)}`); }

      for (const order of data.pedidos || []) {
        try {
          await PrinterService.printPedido({
            mesa: order.mesa,
            pedido: order.pedido,
            quant: order.quantidade,
            extra: order.extra,
            hora: order.hora,
            sendBy: order.sendBy,
          });
          const upd = await fetch(`${API_URL}/updatePrinted`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pedidoId: order.id }),
          });
          if (!upd.ok) {
            const errText = await upd.text();
            console.error(`Falha ao marcar impresso (id=${order.id}): ${upd.status} ${upd.statusText} :: ${errText}`);
          }
        } catch (e) {
          console.log("Erro ao imprimir:", e);
        }
      }
    } catch (error) {
      console.error("Erro ao buscar pedidos pendentes de impressão:", error);
    }
  };

  // ---------- refresh ----------
  refreshData = () => {
    this.setState({ refreshing: true }, () => {
      this.socket.emit("getPedidos", false);
      this.setState({ refreshing: false });
    });
  };

  alterar_estado(id, estado) {
    this.socket.emit('inserir_preparo', { id, estado });
  }

  filtrar = () => {
    this.setState(prevState => ({ showFiltrado: !prevState.showFiltrado }));
  }

  // Modal ingredientes
  extra(index) {
    const { data_filtrado, data } = this.state;
    const list = this.state.showFiltrado ? data_filtrado : data;
    this.setState(prev => ({ showModal: !prev.showModal }));
    this.socket.emit('get_ingredientes', { ingrediente: list[index].pedido});
  }
  GROUP_PALETTE = [
    '#E6F4FF', // azul claro
    '#E8F5E9', // verde claro
    '#FFF3E0', // laranja claro
    '#F3E5F5', // roxo claro
    '#E0F2F1', // teal claro
    '#FFF9C4', // amarelo claro
    '#FCE4EC', // rosa claro
    '#EDE7F6', // lilás claro
    '#DCEDC8', // verde lima claro
    '#FFECB3', // âmbar claro
  ];
  
  normalizeKey = (s) =>
    String(s || '')
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/\s+/g, ' ')
      .trim();
  
  /** chave do grupo = pedido + extra (normalizados) */
  getGroupKey = (item) => {
    const p = this.normalizeKey(item.pedido);
    const e = this.normalizeKey(item.extra);
    return `${p}|${e}`;
  };
  
  /** 
   * Gera contagem e cor por grupo.
   * countMode: 'rows' (nº de linhas iguais) ou 'qty' (soma de item.quantidade)
   */
  buildGroupInfo = (list, countMode = 'rows') => {
    const counts = {};
    const colorByKey = {};
    let colorIdx = 0;
  
    for (const it of list) {
      const key = this.getGroupKey(it);
      if (!(key in counts)) counts[key] = 0;
      counts[key] += countMode === 'qty' ? Number(it.quantidade || 0) : 1;
  
      if (!colorByKey[key]) {
        colorByKey[key] = this.GROUP_PALETTE[colorIdx % this.GROUP_PALETTE.length];
        colorIdx++;
      }
    }
    return { counts, colorByKey };
  };
  
  // ---------- helpers de UI ----------
  actionForEstado = (estado) => {
    if (estado === 'Em Preparo')
      return { label: 'TERMINAR', bg: COLORS.success, txt: '#fff', next: 'Pronto' };
    if (estado === 'A Fazer')
      return { label: 'COMEÇAR',  bg: COLORS.primary, txt: '#fff', next: 'Em Preparo' };
    return { label: 'DESFAZER',   bg: COLORS.danger,  txt: '#fff', next: 'A Fazer' };
  };
  
  

  renderHeader = () => (
    <View style={styles.headerBar}>
      <Text style={styles.headerTitle}>BARMAN • PEDIDOS</Text>
      <TouchableOpacity
        onPress={this.filtrar}
        activeOpacity={0.9}
        style={[styles.toggle, this.state.showFiltrado ? styles.toggleOn : styles.toggleOff]}
      >
        <Text style={this.state.showFiltrado ? styles.toggleTextOn : styles.toggleTextOff}>
          {this.state.showFiltrado ? 'Todos' : 'Filtrar'}
        </Text>
      </TouchableOpacity>
    </View>
  );



  renderItem = ({ item, index }) => {
    const a = this.actionForEstado(item.estado);
  
    const key = this.getGroupKey(item);
    const groupColor = this._groupMeta?.colorByKey?.[key] || '#FFF';
    const dupeCount = this._groupMeta?.counts?.[key] || 1;
  
    return (
      <View style={styles.cardRow}>
        {/* bolha de quantidade + bolinha de duplicados */}
        <View style={styles.qtyWrap}>
          <View style={[styles.qtyBubble, { backgroundColor: groupColor }]}>
            <Text style={styles.qtyText}>{item.quantidade}</Text>
          </View>
  
          {dupeCount > 1 && (
            <View style={[styles.dupeDot, { backgroundColor: groupColor }]}>
              <Text style={styles.dupeText}>{dupeCount}</Text>
            </View>
          )}
        </View>
  
        <View style={styles.middleCol}>
          <Text style={styles.itemName} numberOfLines={1}>
            {item.pedido}
          </Text>
  
          {!!item.extra && (
            <Text style={styles.itemExtra}>
              {item.extra}
            </Text>
          )}
  
          <Text style={styles.comandaText}>
            Comanda {item.comanda}
          </Text>
        </View>
  
        <View style={styles.rightCol}>
          <Text style={styles.timeText}>{item.inicio}</Text>
  
          <TouchableOpacity
            style={styles.infoBtn}
            onPress={() => this.extra(index)}
            hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
          >
            <Text style={styles.infoBtnText}>DETALHES</Text>
          </TouchableOpacity>
  
          <TouchableOpacity
            style={[styles.actionBtn, { backgroundColor: a.bg }]}
            onPress={() => this.alterar_estado(item.id, a.next)}
            activeOpacity={0.85}
          >
            <Text style={[styles.actionText, { color: a.txt }]}>{a.label}</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  };
  

  render() {
    const dataToShow = this.state.showFiltrado ? this.state.data_filtrado : this.state.data;
    const { refreshing, showModal, ingredientes } = this.state;
    const groupMeta = this.buildGroupInfo(dataToShow, 'rows'); // ou 'qty'
    this._groupMeta = groupMeta; // disponibiliza para renderItem

    return (
      <View style={styles.container}>
        <StatusBar barStyle="dark-content" backgroundColor={COLORS.bg} />

        {this.renderHeader()}

        <FlatList
          data={dataToShow}
          keyExtractor={(item, index) => String(item.id ?? index)}
          renderItem={this.renderItem}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={this.refreshData} />
          }
          contentContainerStyle={{ paddingBottom: 24 }}
        />

        <Modal
          animationType="slide"
          transparent
          visible={showModal}
          onRequestClose={() => this.setState({ showModal: false })}
        >
          <View style={styles.modalOverlay}>
            <View style={styles.modalContent}>
              <Text style={styles.modalTitle}>Ingredientes</Text>
              <FlatList
                data={ingredientes}
                keyExtractor={(item, index) => index.toString()}
                renderItem={({ item }) => (
                  <View style={styles.ingRow}>
                    <Text style={styles.ingKey}>{item.key}</Text>
                    <Text style={styles.ingSep}>:</Text>
                    <Text style={styles.ingVal}>{item.dado}</Text>
                  </View>
                )}
              />
              <TouchableOpacity
                style={styles.closeButton}
                onPress={() => this.setState({ showModal: false, ingredientes: [] })}
              >
                <Text style={styles.closeText}>FECHAR</Text>
              </TouchableOpacity>
            </View>
          </View>
        </Modal>
      </View>
    );
  }
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.bg,
    paddingHorizontal: 10,
    paddingTop: 8,
  },

  // Header
  headerBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 6,
    borderBottomWidth: 2,
    borderColor: COLORS.border,
    marginBottom: 6,
  },
  headerTitle: {
    flex: 1,
    fontSize: 20,
    fontWeight: '900',
    color: COLORS.text,
  },
  toggle: {
    borderWidth: 2,
    borderColor: COLORS.border,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 10,
  },
  toggleOn: { backgroundColor: COLORS.chipOn, borderColor: COLORS.border },
  toggleOff:{ backgroundColor: COLORS.chipOff, borderColor: COLORS.border },
  toggleTextOn:  { color: COLORS.chipTextOn, fontWeight: '900' },
  toggleTextOff: { color: COLORS.text,      fontWeight: '900' },

  // Columns header
  columns: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: 2,
    borderColor: COLORS.border,
    backgroundColor: '#F6F6F6',
    marginBottom: 6,
  },
  colText: {
    fontSize: 14,
    fontWeight: '900',
    color: COLORS.text,
  },
  colPedido: { flex: 1 },
  colHora: { width: 88, textAlign: 'center' },
  colAcao: { width: 104, textAlign: 'right' },

  // ROW/CARD mais compacto
cardRow: {
  flexDirection: 'row',
  alignItems: 'flex-start',     // permite múltiplas linhas no meio
  backgroundColor: COLORS.card,
  borderWidth: 2,
  borderColor: COLORS.border,
  borderRadius: 10,
  padding: 6,                   // antes 10
  marginBottom: 6,              // antes 10
},


qtyText: { fontSize: 18, fontWeight: '900', color: COLORS.text }, // antes 20

middleCol: {
  flex: 1,
  justifyContent: 'center',
  paddingRight: 6,              // antes 8
},

itemName: {
  fontSize: 17,                 // antes 18
  fontWeight: '900',
  color: COLORS.text,
  marginBottom: 2,
},

itemExtra: {
  fontSize: 13,                 // antes 14
  fontWeight: '700',
  color: 'blue',
  marginBottom: 2,
  flexWrap: 'wrap',             // permite quebrar linha
  lineHeight: 17,
},

comandaText: {
  fontSize: 13,                 // estava 14
  fontWeight: '800',
  color: COLORS.text,
  lineHeight: 16,
},

rightCol: {
  width: 104,                   // antes 120 (ganha espaço p/ texto)
  alignItems: 'flex-end',
  justifyContent: 'space-between',
},

timeText: {
  fontSize: 14,                 // antes 16
  fontWeight: '900',
  color: COLORS.text,
  marginBottom: 6,
},

infoBtn: {
  backgroundColor: '#FFF',
  borderWidth: 2,
  borderColor: COLORS.border,
  paddingVertical: 5,           // antes 6
  paddingHorizontal: 8,         // antes 10
  borderRadius: 10,
  marginBottom: 6,              // antes 8
},
infoBtnText: {
  fontSize: 12,
  fontWeight: '900',
  color: COLORS.text,
  letterSpacing: 0.5,
},

actionBtn: {
  borderRadius: 10,
  paddingVertical: 8,           // antes 10
  paddingHorizontal: 8,
  minWidth: 100,                // antes 110
  borderWidth: 2,
  borderColor: COLORS.border,
},
actionText: {
  fontSize: 13.5,               // antes 14
  fontWeight: '900',
  textAlign: 'center',
  letterSpacing: 0.5,
},

  
//modal
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.55)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  modalContent: {
    width: '86%',  // menor
    backgroundColor: '#fff',
    borderRadius: 12,
    borderWidth: 2,
    borderColor: COLORS.border,
    padding: 16,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '900',
    marginBottom: 10,
    color: COLORS.text,
    textAlign: 'center',
  },
  ingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: '#E0E0E0',
  },
  ingKey: { width: 120, fontWeight: '800', color: COLORS.text, fontSize: 15 },
  ingSep: { width: 12, textAlign: 'center', color: COLORS.text },
  ingVal: { flex: 1, fontSize: 15, color: COLORS.text },
  closeButton: {
    marginTop: 14,
    backgroundColor: '#FFF4B2',
    borderRadius: 10,
    paddingVertical: 10,
    alignItems: 'center',
    borderWidth: 2,
    borderColor: COLORS.border,
  },
  closeText: { color: COLORS.text, fontSize: 14, fontWeight: '900', letterSpacing: 0.5 },
  qtyWrap: {
    position: 'relative',
    marginRight: 8,
  },
  qtyBubble: {
    width: 40,
    height: 40,
    borderRadius: 20,
    borderWidth: 2,
    borderColor: '#000',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#FFF', // será sobrescrito pela cor do grupo
  },
  dupeDot: {
    position: 'absolute',
    right: -6,
    top: -6,
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 2,
    borderColor: '#000',
    alignItems: 'center',
    justifyContent: 'center',
  },
  dupeText: {
    fontSize: 12,
    fontWeight: '900',
    color: '#000',
  },
  
});
