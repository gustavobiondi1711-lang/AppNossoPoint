import React from 'react';
import {
  ScrollView,
  Modal,
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  Pressable,
  Platform,
  Dimensions,
  KeyboardAvoidingView,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { API_URL } from "./url";
import { UserContext } from '../UserContext';
import { getSocket } from '../socket';

const { height: H } = Dimensions.get('window');
const SHEET_BOTTOM = Math.max(180, Math.floor(H * 0.42)); // sobe mais o sheet

class ComandaScreen extends React.Component {
  static contextType = UserContext;

  constructor(props) {
    super(props);
    const { data, fcomanda, preco, preco_total, preco_pago, username, nomes, ordem } = this.props.route.params;
    this.state = {
      username,
      data,
      dataGeral: data,
      fcomanda,
      preco,
      preco_total,
      preco_pago,
      ordem,
      valor_pago: '',
      guardarValores: [],
      showBotoes: false,
      showLinha1e2: true,
      Brinde: '',
      showBrindeModal: false,
      nomes,
      showAlterarValor: false,
      alterarValorCategoria: '',
      alterarValor: '',
      brindeFiltrado: [],
      brindeFiltradoBase: [],
      itensAlterados: [],
      show_mais: false,

      // Pagamento (novo fluxo unificado)
      opcoesMetodoPag: ['credito', 'debito', 'dinheiro', 'pix'],
      payMode: false,
      paySelections: {},   // { keyDoItem: qtdSelecionadaParaPagar }
      pagandoLoading: false,
      showPayModal: false,
      showPagamentosModal: false,
      pagamentos: [],
      metodoPagSelecionado: null,
      aplicarDez: false,
      caixinhaValor: '',
      ondePaguei: '', // 'itens' | 'parcial' | 'tudo'
    };
    this.socket = null;
  }

  componentDidMount() {
    this.socket = getSocket();
    this.socket.on("preco", this.handlePreco);
    this.socket.on("comanda_deleted", this.handleComandaDeleted);
    this.socket.on("error", this.handleSocketError);
  }
  componentWillUnmount() {
    if (this.socket) {
      this.socket.off("preco", this.handlePreco);
      this.socket.off("comanda_deleted", this.handleComandaDeleted);
      this.socket.off("error", this.handleSocketError);
    }
  }

  // ---------- utils ----------
  normalize = (s) =>
    String(s || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase();

  parseMoney = (v) => {
    const n = parseFloat(String(v ?? '').replace(',', '.'));
    return Number.isFinite(n) ? n : 0;
  };

  // valor base exibido no modal: itens/parcial/tudo
  getModalBase = () => {
    const { ondePaguei, valor_pago, preco } = this.state;
    switch (ondePaguei) {
      case 'itens':
        return this.calcSelectedSubtotal();
      case 'parcial':
        return this.parseMoney(valor_pago); // input digitado
      case 'tudo':
        return this.parseMoney(preco);      // valor a pagar da comanda
      default:
        return 0;
    }
  };

  // --- helpers de item
  keyForItem = (it, idx) => `${it?.id ?? ''}|${it?.pedido ?? ''}|${it?.extra ?? ''}|${idx}`;
  getInt = (v, d=0) => { const n = parseInt(v, 10); return Number.isFinite(n) ? n : d; };
  getRestante = (it) => Math.max(0, this.getInt(it?.quantidade) - this.getInt(it?.quantidade_paga));
  getUnitPrice = (it) => {
    const q = parseFloat(it?.quantidade || '0');
    const p = parseFloat(it?.preco || '0');
    if (!Number.isFinite(q) || q <= 0) return 0;
    return p / q;
  };

  // soma o subtotal selecionado (sem 10%)
  calcSelectedSubtotal = () => {
    const { data, paySelections } = this.state;
    let total = 0;
    for (let i = 0; i < data.length; i++) {
      const it = data[i];
      const key = this.keyForItem(it, i);
      const sel = this.getInt(paySelections[key], 0);
      if (sel > 0) total += sel * this.getUnitPrice(it);
    }
    return total;
  };

  // --- entrar/sair do modo de pagamento
  enterPayMode = () => {
    this.setState({ payMode: true, paySelections: {}, showBotoes: false, showLinha1e2: false });
  };
  exitPayMode = () => {
    this.setState({ payMode: false, paySelections: {}, showLinha1e2: true });
  };

  // --- selecionar qtd p/ item
  incPay = (idx) => {
    const it = this.state.data[idx];
    const restante = this.getRestante(it);
    if (restante <= 0) return;
    const key = this.keyForItem(it, idx);
    const atual = this.state.paySelections[key] || 0;
    if (atual < restante) {
      this.setState({ paySelections: { ...this.state.paySelections, [key]: atual + 1 } });
    }
  };
  decPay = (idx) => {
    const it = this.state.data[idx];
    const key = this.keyForItem(it, idx);
    const atual = this.state.paySelections[key] || 0;
    if (atual > 0) {
      const novo = { ...this.state.paySelections, [key]: atual - 1 };
      if (novo[key] === 0) delete novo[key];
      this.setState({ paySelections: novo });
    }
  };

  alertaConfirmPayItems = () => {
    const subtotal = this.calcSelectedSubtotal();
    if (subtotal <= 0) {
      alert('Selecione ao menos 1 unidade para pagar.');
      return;
    }
    this.setState({
      showPayModal: true,
      ondePaguei: 'itens',
      metodoPagSelecionado: null,
      aplicarDez: false,
      caixinhaValor: '',
    });
  };

  fecharPayModal = () => {
    this.setState({
      showPayModal: false,
      metodoPagSelecionado: null,
      aplicarDez: false,
      caixinhaValor: '',
    });
  };

  confirmarPagamentoComEscolhas = () => {
    const { metodoPagSelecionado, ondePaguei } = this.state;
    if (!metodoPagSelecionado) {
      alert('Selecione um método de pagamento.');
      return;
    }
    if (ondePaguei === 'itens') {
      this.confirmPayItems();
    } else if (ondePaguei === 'parcial') {
      this.confirmarParcialUnified();
    } else if (ondePaguei === 'tudo') {
      this.confirmarTudoPagoUnified();
    }
  };

  confirmarParcialUnified = () => {
    const {
      valor_pago, fcomanda, preco,
      metodoPagSelecionado, caixinhaValor, aplicarDez
    } = this.state;

    const valorNum = this.parseMoney(valor_pago);
    const max = this.parseMoney(preco);
    if (!valorNum || valorNum <= 0 || valorNum > max) {
      alert('Insira um valor válido para pagamento parcial.');
      return;
    }

    const dez_por_cento = aplicarDez ? base * 0.10 : null;


    try {
      this.setState({ pagandoLoading: true });
      this.socket.emit('faturamento', true);
      this.socket.emit('pagar_parcial', {
        valor_pago: valorNum,
        fcomanda,
        caixinha:caixinhaValor,
        dez_por_cento: dez_por_cento,
        forma_de_pagamento: metodoPagSelecionado,
      });

      this.setState(prev => ({
        preco: (this.parseMoney(prev.preco) - valorNum).toFixed(2),
        valor_pago: '',
        showPayModal: false,
        metodoPagSelecionado: null,
        aplicarDez: false,
        caixinhaValor: '',
      }));
    } catch (e) {
      console.log('Falha ao pagar parcial:', e);
      alert('Não foi possível pagar parcialmente agora.');
    } finally {
      this.setState({ pagandoLoading: false });
    }
  };

  confirmarTudoPagoUnified = () => {
    const { fcomanda, preco, metodoPagSelecionado, caixinhaValor, aplicarDez } = this.state;
    const base = this.parseMoney(preco);
    if (!(base > 0)) {
      alert('Não há valor para pagar.');
      return;
    }

    const cxTyped = this.parseMoney(caixinhaValor);
    const dez_por_cento = aplicarDez ? base * 0.10 : null;

    try {
      this.setState({ pagandoLoading: true });
      this.socket.emit('delete_comanda', {
        fcomanda,
        valor_pago: preco,
        caixinha:caixinhaValor,
        dez_por_cento: dez_por_cento,
        forma_de_pagamento: metodoPagSelecionado,
      });

      this.setState({
        showPayModal: false,
        metodoPagSelecionado: null,
        aplicarDez: false,
        caixinhaValor: '',
        valor_pago: '',
      });
    } catch (e) {
      console.log('Falha ao finalizar tudo pago:', e);
      alert('Não foi possível finalizar agora.');
    } finally {
      this.setState({ pagandoLoading: false });
    }
  };
  // formata simples
fmtBRL = (v) => {
  const n = parseFloat(String(v ?? '').replace(',', '.'));
  return `R$ ${Number.isFinite(n) ? n.toFixed(2) : '0.00'}`;
};
// Lê e normaliza o campo opcoes (string JSON, array ou objeto)
parseOpcoes = (raw) => {
  try {
    const j = typeof raw === 'string' ? JSON.parse(raw) : raw;
    let groups = Array.isArray(j) ? j : (j?.groups || j?.opcoes || j?.options || []);
    if (!Array.isArray(groups)) groups = [];
    return groups.map(g => {
      let opts = g?.options ?? g?.opcoes ?? [];
      if (!Array.isArray(opts)) opts = [];
      return { options: opts };
    });
  } catch {
    return [];
  }
};

// true se existir ALGUMA option com valor_extra > 0
hasExtrasComValor = (it) => {
  const groups = this.parseOpcoes(it?.opcoes);
  for (const g of groups) {
    for (const o of (g.options || [])) {
      if (Number(o?.valor_extra || 0) > 0) return true;
    }
  }
  return false;
};

// Texto "Opções: ..." apenas com as de valor_extra > 0
extrasLabel = (it) => {
  const groups = this.parseOpcoes(it?.opcoes);
  const list = [];
  for (const g of groups) {
    for (const o of (g.options || [])) {
      const v = Number(o?.valor_extra || 0);
      if (v > 0) list.push(`${o.nome} (+R$ ${v.toFixed(2).replace('.', ',')})`);
    }
  }
  return list.join(', ');
};

// parse das opções selecionadas (o que foi salvo no campo "opcoes")
parseOpcoesSelecionadas = (raw) => {
  if (!raw) return [];
  let data = raw;
  try {
    if (typeof raw === 'string') data = JSON.parse(raw);
  } catch {
    return [];
  }
  if (!Array.isArray(data)) return [];         // esperado: lista de grupos
  // flatten: retorna apenas as options de cada grupo
  const out = [];
  for (const g of data) {
    const options = Array.isArray(g?.options) ? g.options : [];
    for (const o of options) {
      const nome = o?.nome ?? '';
      const valor_extra = parseFloat(o?.valor_extra ?? 0) || 0;
      out.push({ nome, valor_extra });
    }
  }
  return out;
};

// retorna SOMENTE as opções com extra > 0
getSelectedExtras = (it) => {
  const arr = this.parseOpcoesSelecionadas(it?.opcoes);
  return arr.filter(o => (parseFloat(o.valor_extra) || 0) > 0);
};

// condição para exibir opções (seguindo seu critério)
shouldShowOptions = (it) => {
  const preco = parseFloat(String(it?.preco ?? '0').replace(',', '.')) || 0;
  // se vier do backend, usa; senão cai no unitário calculado
  const preco_unitario_backend = parseFloat(String(it?.preco_unitario ?? '').replace(',', '.'));
  const unitCalc = this.getUnitPrice(it); // já existe na sua classe
  const pu = Number.isFinite(preco_unitario_backend) ? preco_unitario_backend : unitCalc;
  return preco > 0 && pu < preco;
};

  // --- confirmar pagamento dos itens selecionados
  confirmPayItems = async () => {
    const { paySelections, data, fcomanda, aplicarDez, metodoPagSelecionado, caixinhaValor, preco } = this.state;
    const keys = Object.keys(paySelections);
    if (keys.length === 0) {
      alert('Selecione ao menos 1 unidade para pagar.');
      return;
    }
    if (!metodoPagSelecionado) {
      alert('Selecione um método de pagamento.');
      return;
    }

    const itens = [];
    for (let i = 0; i < data.length; i++) {
      const it = data[i];
      const key = this.keyForItem(it, i);
      const qtd = this.getInt(paySelections[key], 0);
      if (qtd > 0) {
        itens.push({
          index: i,
          id: it?.id ?? null,
          pedido: it?.pedido ?? '',
          extra: it?.extra ?? '',
          quantidade: qtd,
        });
      }
    }
    if (itens.length === 0) {
      alert('Nada selecionado para pagar.');
      return;
    }

    const cxNum = this.parseMoney(caixinhaValor);
    const caixinha = cxNum > 0 ? cxNum : null;

    try {
      this.setState({ pagandoLoading: true });

      this.socket.emit('pagar_itens', {
        comanda: fcomanda,
        itens,
        forma_de_pagamento: metodoPagSelecionado,
        aplicarDez,
        caixinha,
      });

      this.setState({
        payMode: false,
        paySelections: {},
        showPayModal: false,
        metodoPagSelecionado: null,
        showLinha1e2: true,
        aplicarDez: false,
        caixinhaValor: '',
      });
    } catch (e) {
      console.log('Falha ao pagar itens:', e);
      alert('Não foi possível pagar os itens agora.');
    } finally {
      this.setState({ pagandoLoading: false });
    }
  };

  // --------- socket handlers ---------
  handlePreco = (data) => {
    if (!data) return;
    if (data.comanda === this.state.fcomanda) {
      if (data.nomes) this.setState({ nomes: data.nomes });
      this.setState({
        data: data.dados ?? [],
        dataGeral: data.dados ?? [],
        preco: data.preco_a_pagar ?? 0,
        preco_pago: data.preco_pago ?? 0,
        preco_total: data.preco_total ?? 0,
      });
    }
  };
  handleComandaDeleted = ({ fcomanda }) => {
    if (fcomanda === this.state.fcomanda) {
      this.setState({ data: [], dataGeral: [], nomes: [], preco: 0, preco_total: 0, preco_pago: 0 });
    }
  };
  handleSocketError = ({ message }) => console.error("Erro do servidor:", message);

  // --------- ações de edição ---------
  aparecerBotoes = () => {
    const copia = JSON.parse(JSON.stringify(this.state.data));
    this.setState({ guardarValores: copia, showBotoes: true });
  };
  cancelar = () => {
    this.setState({ data: this.state.guardarValores, itensAlterados:[], showBotoes: false });
  };
  confirmar = () => {
    const { itensAlterados, fcomanda } = this.state;
    const { user } = this.context || {};
    this.socket.emit('atualizar_comanda', {
      itensAlterados,
      comanda: fcomanda,
      username: user?.username,
      token: user?.token,
    });
    this.setState({ showBotoes: false, itensAlterados: [] });
  };

  apagarPedidos = (index) => {
    const arr = [...this.state.data];
    const it = { ...arr[index] };
    const pu = parseFloat(it.preco) / parseFloat(it.quantidade || 1);
    it.preco = (parseFloat(it.preco) - pu).toString();
    it.quantidade = (parseInt(it.quantidade) - 1).toString();
    if (parseInt(it.quantidade) >= 0) {
      arr[index] = it;
      this.setState({ data: arr });
      this.atualizarItensAlterados(it);
    }
  };
  adicionarPedidos = (index) => {
    const arr = [...this.state.data];
    const it = { ...arr[index] };
    const pu = parseFloat(it.preco) / parseFloat(it.quantidade || 1);
    it.preco = (parseFloat(it.preco) + pu).toString();
    it.quantidade = (parseInt(it.quantidade) + 1).toString();
    arr[index] = it;
    this.setState({ data: arr });
    this.atualizarItensAlterados(it);
  };
  atualizarItensAlterados = (itemAtualizado) => {
    this.setState(prev => {
      const existe = prev.itensAlterados.some(
        (i) =>
          i.pedido === itemAtualizado.pedido &&
          parseFloat(i.preco) / parseFloat(i.quantidade) ===
            parseFloat(itemAtualizado.preco) / parseFloat(itemAtualizado.quantidade)
      );
      const nova = existe
        ? prev.itensAlterados.map((i) => (i.pedido === itemAtualizado.pedido ? itemAtualizado : i))
        : [...prev.itensAlterados, itemAtualizado];
      return { itensAlterados: nova };
    });
  };

  // --------- brindes ---------
  changeBrinde = (rawInput) => {
    const base = Array.isArray(this.state.brindeFiltradoBase) ? this.state.brindeFiltradoBase : [];
    const raw = String(rawInput.toLowerCase() ?? '');
    const qNorm = this.normalize(raw);
    const words = qNorm.trim().split(/\s+/).filter(Boolean);

    if (words.length === 0) {
      this.setState({ brindeFiltrado: [], Brinde: raw });
      return;
    }

    const starts = [];
    const allWords = [];
    const includes = [];

    for (let i = 0; i < base.length; i++) {
      const it = base[i];
      const nameNorm = this.normalize(it);
      if (!nameNorm) continue;

      let matched = false;
      for (const w of words) {
        if (nameNorm.startsWith(w)) { starts.push(it); matched = true; break; }
      }
      if (matched) continue;

      if (words.length > 1 && words.every((w) => nameNorm.includes(w))) {
        allWords.push(it);
        continue;
      }

      for (const w of words) {
        if (nameNorm.includes(w)) { includes.push(it); break; }
      }
    }

    const seen = new Set();
    const resultado = [];
    for (const bucket of [starts, allWords, includes]) {
      for (const it of bucket) {
        if (!seen.has(it)) { seen.add(it); resultado.push(it); }
      }
    }

    this.setState({ brindeFiltrado: resultado, Brinde: raw });
  };

  confirmarBrinde = () => {
    const { fcomanda, Brinde, username } = this.state;
    const horario = new Date().toTimeString().slice(0, 5);
    this.socket.emit('insert_order', {
      comanda: fcomanda,
      pedidosSelecionados: [Brinde],
      quantidadeSelecionada: [1],
      preco: true,
      username,
      horario,
      extraSelecionados: [''],
    });
    this.setState({ Brinde: '' });
  };

  // --------- ordem / filtros ---------
  atualizarOrdem = (sinal, ordem) => {
    if (sinal === '-' && this.state.ordem > 0) {
      this.setState({ ordem: ordem - 1 });
      fetch(`${API_URL}/pegar_pedidos`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comanda: this.state.fcomanda, ordem: ordem - 1 }),
      }).then(r => r.json()).then(data => {
        if (data?.data) this.setState({ data: data.data, dataGeral: data.data, preco: data.preco });
      }).catch(console.error);
    } else if (sinal === '+') {
      this.setState({ ordem: ordem + 1 });
      fetch(`${API_URL}/pegar_pedidos`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comanda: this.state.fcomanda, ordem: ordem + 1 }),
      }).then(r => r.json()).then(data => {
        if (data?.data) this.setState({ data: data.data, dataGeral: data.data, preco: data.preco });
      }).catch(console.error);
    }
  };

  desfazerPagamento = () => {
    this.socket.emit('desfazer_pagamento', { comanda: this.state.fcomanda, preco: this.state.preco, ordem: this.state.ordem });
    this.setState({ ordem: 0 });
  };

  dataComnpleto = () => this.setState({ data: this.state.dataGeral });
  filtrarPorNome(nome) { this.setState({ data: this.state.dataGeral.filter(i => i.nome === nome) }); }

  confirmarValor = () => {
    const { alterarValor, alterarValorCategoria, fcomanda } = this.state;
    this.socket.emit('alterarValor', { valor: alterarValor, categoria: alterarValorCategoria, comanda: fcomanda });
    this.setState({ showAlterarValor: false, alterarValor: '', alterarValorCategoria: '' });
  };
  openPagamentos = async () => {
    const { fcomanda } = this.state;
    this.setState({ showPagamentosModal: true, pagamentosLoading: true });
  
    try {
      const resp = await fetch(`${API_URL}/pegar_pagamentos_comanda`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comanda: fcomanda }),
      });
      const json = await resp.json();
  
      // aceita vários formatos de retorno
      const pagamentos = Array.isArray(json)
        ? json
        : (json?.pagamentos || json?.data || []);
  
      this.setState({ pagamentos, pagamentosLoading: false });
    } catch (e) {
      this.setState({ pagamentosLoading: false });
      Alert.alert('Erro', 'Não foi possível carregar os pagamentos.');
    }
  };
  
  closePagamentosModal = () => {
    this.setState({ showPagamentosModal: false, pagamentos: [] });
  };
  
  excluirPagamento = (pagamento) => {
    const id = pagamento?.id ?? pagamento?.id_pagamento ?? pagamento?.pagamento_id;
    if (!id) return;
  
    Alert.alert(
      'Excluir pagamento',
      'Tem certeza que deseja excluir este pagamento?',
      [
        { text: 'Cancelar', style: 'cancel' },
        { text: 'Excluir', style: 'destructive', onPress: () => this._doExcluirPagamento(id) },
      ],
    );
  };
  
  _doExcluirPagamento = async (pagamentoId) => {
    const { fcomanda } = this.state;
    try {
      const resp = await fetch(`${API_URL}/excluir_pagamento`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ comanda: fcomanda, pagamento_id: pagamentoId }),
      });
      const ok = resp.ok;
      if (!ok) throw new Error('HTTP');
  
      // remove localmente
      this.setState(prev => ({
        pagamentos: prev.pagamentos.filter(p => {
          const idP = p?.id ?? p?.id_pagamento ?? p?.pagamento_id;
          return idP !== pagamentoId;
        }),
      }));
  
      // pede refresh do resumo via socket (se seu backend emitir "preco")
      if (this.socket) this.socket.emit('faturamento', true);
    } catch (e) {
      Alert.alert('Erro', 'Não foi possível excluir o pagamento.');
    }
  };
  

  selecionarOpcao = (item) => {
    this.setState({ show_mais: false });

    if (item === 'Editar') {
      if (this.state.payMode) this.setState({ payMode: false, paySelections: {} });
      this.aparecerBotoes();
      return;
    }

    if (item === 'desconto') {
      this.setState({ alterarValorCategoria: item, showAlterarValor: true });
      return;
    }

    if (item === 'Brinde') {
      if (!this.state.brindeFiltradoBase || this.state.brindeFiltradoBase.length === 0) {
        this.socket.once('respostaCardapio', (data) => {
          if (data?.dataCardapio) {
            this.setState({ brindeFiltradoBase: data.dataCardapio.map(i => i.item) });
          }
        });
        this.socket.emit('getCardapio', false);
      }
      this.setState({ showBrindeModal: true, Brinde: '', brindeFiltrado: [] });
      return;
    }
    if (item === 'Pagamentos') {
    this.openPagamentos(); // <<< novo
    return;
    }
  };

  mostrarOpcoes = () => this.setState({ show_mais: true, showAlterarValor: false });

  // --------- modais ---------
  renderPagamentosModal() {
    const { showPagamentosModal, pagamentos, pagamentosLoading } = this.state;
    if (!showPagamentosModal) return null;
  
    const money = (v) => `R$ ${this.parseMoney(v).toFixed(2)}`;
  
    return (
      <Modal
        transparent
        visible={showPagamentosModal}
        animationType="fade"
        onRequestClose={this.closePagamentosModal}
      >
        <KeyboardAvoidingView
          style={styles.modalAvoider}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          keyboardVerticalOffset={Platform.OS === 'ios' ? 64 : 24}
        >
          <Pressable style={styles.modalBackdrop} onPress={this.closePagamentosModal} />
          <View style={styles.bigModal}>
            <Text style={styles.bigModalTitle}>Pagamentos da Comanda</Text>
  
            {pagamentosLoading ? (
              <View style={styles.centerBox}>
                <ActivityIndicator size="large" />
                <Text style={{ marginTop: 8, color: '#374151' }}>Carregando...</Text>
              </View>
            ) : pagamentos.length === 0 ? (
              <View style={styles.centerBox}>
                <Text style={{ color: '#6b7280' }}>Nenhum pagamento encontrado.</Text>
              </View>
            ) : (
              <ScrollView style={{ maxHeight: 360 }}>
                {pagamentos.map((p, idx) => {
                  const id = p?.id ?? p?.id_pagamento ?? p?.pagamento_id;
                  const valor = p?.valor ?? p?.valor_pago ?? p?.total ?? 0;
                  const forma = p?.forma_de_pagamento ?? p?.metodo ?? p?.forma ?? '—';
                  const caixinha = p?.caixinha ?? 0;
                  const quando = p?.data ?? p?.criado_em ?? p?.horario ?? '';
  
                  return (
                    <View key={`${id ?? idx}`} style={styles.paymentItem}>
                      <View style={styles.paymentMainRow}>
                        <View style={styles.paymentLeft}>
                          <Text style={styles.paymentValue}>{money(valor)}</Text>
                          {!!caixinha && <Text style={styles.paymentMeta}>Caixinha: {money(caixinha)}</Text>}
                          <Text style={styles.paymentMeta}>Forma: {String(forma).toUpperCase()}</Text>
                          {!!quando && <Text style={styles.paymentMeta}>Quando: {quando}</Text>}
                          {!!id && <Text style={styles.paymentMetaMuted}>ID: {id}</Text>}
                        </View>
                        {!!id && (
                          <TouchableOpacity style={styles.paymentDeleteBtn} onPress={() => this.excluirPagamento(p)}>
                            <Text style={styles.paymentDeleteText}>Excluir</Text>
                          </TouchableOpacity>
                        )}
                      </View>
                    </View>
                  );
                })}
              </ScrollView>
            )}
  
            <View style={[styles.miniActions, { marginTop: 16 }]}>
              <TouchableOpacity style={[styles.miniBtn, styles.miniBtnPrimary]} onPress={this.closePagamentosModal}>
                <Text style={styles.miniBtnPrimaryText}>Fechar</Text>
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    );
  }
  
  renderOpcoesModal() {
    const { show_mais } = this.state;
    const opcoes = ['Editar', 'desconto', 'Brinde','Pagamentos'];
    if (!show_mais) return null;
    return (
      <Modal transparent visible={show_mais} animationType="fade" onRequestClose={() => this.setState({ show_mais: false })}>
        <Pressable style={styles.sheetBackdrop} onPress={() => this.setState({ show_mais: false })} />
        <View style={[styles.sheetContainer, { bottom: SHEET_BOTTOM }]}>
          <View style={styles.sheetHandle} />
          <Text style={styles.sheetTitle}>Opções</Text>

          {opcoes.map((label, idx) => (
            <TouchableOpacity key={idx} style={styles.sheetItem} activeOpacity={0.8} onPress={() => this.selecionarOpcao(label)}>
              <Text style={styles.sheetItemText}>{label}</Text>
            </TouchableOpacity>
          ))}

          <TouchableOpacity style={styles.sheetCancel} activeOpacity={0.8} onPress={() => this.setState({ show_mais: false })}>
            <Text style={styles.sheetCancelText}>Fechar</Text>
          </TouchableOpacity>
        </View>
      </Modal>
    );
  }

  renderAlterarValorModal() {
    const { showAlterarValor, alterarValor, alterarValorCategoria } = this.state;
    if (!showAlterarValor) return null;
    return (
      <Modal transparent visible={showAlterarValor} animationType="fade" onRequestClose={() => this.setState({ showAlterarValor: false })}>
        <KeyboardAvoidingView
          style={styles.modalAvoider}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          keyboardVerticalOffset={Platform.OS === 'ios' ? 64 : 24}
        >
          <Pressable style={styles.modalBackdrop} onPress={() => this.setState({ showAlterarValor: false })} />
          <View style={styles.miniModal}>
            <Text style={styles.miniModalTitle}>{alterarValorCategoria === 'caixinha' ? 'Caixinha' : 'Desconto'}</Text>
            <TextInput
              keyboardType="numeric"
              placeholder="Valor"
              placeholderTextColor="#999"
              onChangeText={(alterarValor) => this.setState({ alterarValor })}
              value={alterarValor}
              style={styles.miniInput}
            />
            <View style={styles.miniActions}>
              <TouchableOpacity style={[styles.miniBtn, styles.miniBtnGhost]} onPress={() => this.setState({ showAlterarValor: false, alterarValor: '' })}>
                <Text style={styles.miniBtnGhostText}>Cancelar</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.miniBtn, styles.miniBtnPrimary]} onPress={this.confirmarValor}>
                <Text style={styles.miniBtnPrimaryText}>OK</Text>
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    );
  }

  renderBrindeModal() {
    const { showBrindeModal, Brinde, brindeFiltrado = [] } = this.state;
    if (!showBrindeModal) return null;
    return (
      <Modal transparent visible={showBrindeModal} animationType="fade" onRequestClose={() => this.setState({ showBrindeModal: false })}>
        <KeyboardAvoidingView
          style={styles.modalAvoider}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          keyboardVerticalOffset={Platform.OS === 'ios' ? 64 : 24}
        >
          <Pressable style={styles.modalBackdrop} onPress={() => this.setState({ showBrindeModal: false, brindeFiltrado: [] })} />
          <View style={styles.miniModal}>
            <Text style={styles.miniModalTitle}>Brinde</Text>
            <TextInput
              placeholder="Buscar brinde"
              placeholderTextColor="#999"
              onChangeText={this.changeBrinde}
              value={Brinde}
              style={styles.miniInput}
              autoComplete="off"
              autoCorrect={false}
              spellCheck={false}
              textContentType="none"
              importantForAutofill="no"
            />
            {brindeFiltrado.length > 0 && (
              <View style={styles.sugestoesBox}>
                {brindeFiltrado.slice(0, 5).map((sug, i) => (
                  <TouchableOpacity key={`${sug}-${i}`} style={styles.sugestaoItem} onPress={() => this.setState({Brinde:sug,brindeFiltrado:[]})}>
                    <Text style={styles.sugestaoText}>{sug}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            )}
            <View style={styles.miniActions}>
              <TouchableOpacity
                style={[styles.miniBtn, styles.miniBtnGhost]}
                onPress={() => this.setState({ showBrindeModal: false, Brinde: '', brindeFiltrado: [] })}
              >
                <Text style={styles.miniBtnGhostText}>Cancelar</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.miniBtn, styles.miniBtnPrimary]}
                onPress={() => { this.confirmarBrinde(); this.setState({ showBrindeModal: false, brindeFiltrado: [] }); }}
              >
                <Text style={styles.miniBtnPrimaryText}>OK</Text>
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    );
  }

  // --------- UI: nomes / tabela / resumo ---------
  renderNomesRow() {
    const { nomes, ordem } = this.state;
    if (!Array.isArray(nomes) || nomes.length === 0 || ordem !== 0) return null;
    return (
      <View style={styles.nomeRow}>
        <TouchableOpacity style={[styles.chipBtn, styles.chipNeutral]} onPress={this.dataComnpleto}><Text style={styles.chipText}>Geral</Text></TouchableOpacity>
        {nomes.map((n, i) => (
          <View key={i} style={styles.nomeButtonWrapper}>
            <TouchableOpacity style={[styles.chipBtn, styles.chipNeutral]} onPress={() => this.filtrarPorNome(n.nome)}>
              <Text style={styles.chipText}>{n.nome}</Text>
            </TouchableOpacity>
          </View>
        ))}
        <TouchableOpacity style={[styles.chipBtn, styles.chipWarn]} onPress={() => this.filtrarPorNome('-1')}><Text style={styles.chipText}>Sem Nome</Text></TouchableOpacity>
      </View>
    );
  }

  renderTabelaPedidos() {
    const { data, showBotoes, payMode, paySelections } = this.state;
    if (!data || data.length === 0) return null;

    const naoPagos = [];
    const pagos = [];

    for (let i = 0; i < data.length; i++) {
      const it = data[i];
      const qtd = this.getInt(it?.quantidade);
      const qtdPaga = this.getInt(it?.quantidade_paga);
      const restante = Math.max(0, qtd - qtdPaga);

      if (!qtd) continue;
      if (qtdPaga > 0) pagos.push({ it, index: i, qtdPaga });
      if (restante > 0) naoPagos.push({ it, index: i, restante });
    }

    const RowNaoPago = ({ it, index, restante }) => {
      const key = this.keyForItem(it, index);
      const sel = paySelections[key] || 0;

      return (
        <View key={`np-${index}`} style={styles.tableRow}>
           <View style={{ flex: 2 }}>
            <Text style={styles.itemText} numberOfLines={2}>
              {it.pedido} {it.extra}
            </Text>
            {this.hasExtrasComValor(it) && (
              <Text style={styles.itemExtrasText} numberOfLines={2}>
                Opções: {this.extrasLabel(it)}
              </Text>
            )}
          </View>

          <Text style={[styles.itemText, { flex: 0.8, textAlign: 'center' }]}>{restante}</Text>
          <Text style={[styles.itemText, { flex: 0.9, textAlign: 'right' }]}>{it.preco}</Text>

          {showBotoes && (
            <View style={styles.editControls}>
              <TouchableOpacity style={[styles.miniSquare, styles.danger]} onPress={() => this.apagarPedidos(index)}>
                <Text style={styles.miniSquareText}>-</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.miniSquare, styles.primary]} onPress={() => this.adicionarPedidos(index)}>
                <Text style={styles.miniSquareText}>+</Text>
              </TouchableOpacity>
            </View>
          )}

          {payMode && (
            <View style={styles.payControls}>
              <TouchableOpacity style={[styles.payBtn, styles.payMinus]} onPress={() => this.decPay(index)}>
                <Text style={styles.payBtnText}>-</Text>
              </TouchableOpacity>
              <Text style={styles.payQtyText}>{sel || 0}</Text>
              <TouchableOpacity style={[styles.payBtn, styles.payPlus]} onPress={() => this.incPay(index)}>
                <Text style={styles.payBtnText}>+</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>
      );
    };


  
      const RowPago = ({ it, index, qtdPaga }) => (
        <View key={`pg-${index}`} style={styles.tableRow}>
          <View style={{ flex: 2 }}>
            <Text style={styles.itemText} numberOfLines={2}>
              {it.pedido} {it.extra}
            </Text>
            {this.hasExtrasComValor(it) && (
              <Text style={styles.itemExtrasText} numberOfLines={2}>
                Opções: {this.extrasLabel(it)}
              </Text>
            )}
          </View>

          <Text style={[styles.itemText, { flex: 0.8, textAlign: 'center' }]}>{qtdPaga}</Text>
          <Text style={[styles.itemText, { flex: 0.9, textAlign: 'right', color: '#059669' }]}>
            Pago
          </Text>
        </View>
      );

      return (
        <View>
          {pagos.length > 0 && (
            <>
              <Text style={[styles.sectionTitle, { marginTop: 12 }]}>Pagos</Text>
              {pagos.map(({ it, index, qtdPaga }) => (
                <RowPago key={`pg-${index}`} it={it} index={index} qtdPaga={qtdPaga} />
              ))}
            </>
          )}

          {naoPagos.length > 0 && (
            <>
              <Text style={styles.sectionTitle}>Não pagos</Text>
              {naoPagos.map(({ it, index, restante }) => (
                <RowNaoPago key={`np-${index}`} it={it} index={index} restante={restante} />
              ))}
            </>
          )}
        </View>
      );
    }

  // abre o modal de pagamento e define o contexto
  abrirModalPagamento = (tipo) => {
    this.setState({
      showPayModal: true,
      ondePaguei: tipo, // 'tudo' | 'parcial' | 'itens'
      metodoPagSelecionado: null,
      aplicarDez: false,
      caixinhaValor: '',
    });
  };

  // resumo + botões de ação
  renderResumoPagamento() {
    const { ordem, preco_pago, preco, preco_total, valor_pago, showLinha1e2,data } = this.state;

    if (ordem !== 0) {
      return (
        <View style={{ marginTop: 10 }}>
          {ordem === 1 && data && data.length>0? (
            <TouchableOpacity style={[styles.chipBtn, styles.chipDanger]} onPress={this.desfazerPagamento}>
              <Text style={styles.chipText}>Desfazer Último Pagamento</Text>
            </TouchableOpacity>
          ) : (
            <Text>não é possível desfazer o pagamento</Text>
          )}
        </View>
      );
    }

    return (
      <View>
        <View style={styles.summaryBox}>
          {/* Valores principais */}
          <View style={styles.paymentRow}>
            <View style={styles.paymentBlock}>
              <Text style={styles.totalText}>Valor Pago</Text>
              <Text style={styles.totalValue}>{preco_pago}</Text>
            </View>
            <View style={styles.paymentBlock}>
              <Text style={styles.totalText}>Valor a Pagar</Text>
              <Text style={styles.totalValue}>{preco}</Text>
            </View>
            <View style={styles.paymentBlock}>
              <Text style={styles.totalText}>Valor Total</Text>
              <Text style={styles.totalValue}>{preco_total}</Text>
            </View>
          </View>

          {showLinha1e2 && (
            <>
              {/* Linha 1: parcial */}
              <View style={styles.parcialRow}>
                <TextInput
                  placeholder="Quanto?"
                  placeholderTextColor="#999"
                  onChangeText={(valor_pago) => this.setState({ valor_pago })}
                  value={valor_pago}
                  keyboardType="numeric"
                  style={styles.input}
                />
                <TouchableOpacity
                  style={[styles.chipBtn, styles.primary]}
                  onPress={() => this.abrirModalPagamento('parcial')}
                >
                  <Text style={styles.chipText}>Pagar Parcial</Text>
                </TouchableOpacity>
              </View>

              {/* Linha 2: tudo pago + pagar itens */}
              <View style={[styles.buttonRow, { marginTop: 20 }]}>
                <TouchableOpacity
                  style={[styles.chipBtn, styles.primary, { minWidth: 120 }]}
                  onPress={() => this.abrirModalPagamento('tudo')}
                >
                  <Text style={styles.chipText}>Tudo Pago</Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.chipBtn, styles.primary, { minWidth: 120 }]}
                  onPress={this.enterPayMode}
                >
                  <Text style={styles.chipText}>Pagar Itens</Text>
                </TouchableOpacity>
              </View>
            </>
          )}
        </View>
      </View>
    );
  }

  // --------- render ---------
  render() {
    const { fcomanda, ordem, showBotoes, payMode, show_mais } = this.state;

    return (
      <View style={{ flex: 1 }}>
        <ScrollView style={styles.container} contentContainerStyle={{ paddingBottom: 24 }}>
          {/* HEADER */}
          <View style={styles.headerRow}>
            <Text style={styles.title} numberOfLines={1} ellipsizeMode="tail">
              Comanda {fcomanda}
            </Text>

            <View style={styles.headerControls}>
              {!payMode && !showBotoes && (
                <View style={styles.navGroup}>
                  <TouchableOpacity style={styles.navBtn} onPress={() => this.atualizarOrdem('+', ordem)}>
                    <Text style={styles.navBtnText}>{"<"}</Text>
                  </TouchableOpacity>
                  <Text style={styles.ordemText}>{ordem}</Text>
                  <TouchableOpacity style={styles.navBtn} onPress={() => this.atualizarOrdem('-', ordem)}>
                    <Text style={styles.navBtnText}>{">"}</Text>
                  </TouchableOpacity>
                </View>
              )}

              {payMode ? (
                <View style={styles.inlineActions}>
                  <TouchableOpacity style={[styles.chipBtn, styles.chipDanger]} onPress={this.exitPayMode}>
                    <Text style={styles.chipText}>Cancelar</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.chipBtn, styles.primary]}
                    onPress={this.alertaConfirmPayItems}
                    disabled={this.state.pagandoLoading}
                  >
                    <Text style={styles.chipText}>
                      {this.state.pagandoLoading ? 'Enviando...' : 'Confirmar Pagamento'}
                    </Text>
                  </TouchableOpacity>
                </View>
              ) : (
                <>
                  {!showBotoes ? (
                    <>
                      {this.renderOpcoesModal()}
                      {!show_mais && this.state.ordem === 0 && (
                        <TouchableOpacity style={styles.fab} activeOpacity={0.85} onPress={this.mostrarOpcoes}>
                          <Text style={styles.fabPlus}>+</Text>
                        </TouchableOpacity>
                      )}
                    </>
                  ) : (
                    <View style={styles.inlineActions}>
                      <TouchableOpacity style={[styles.chipBtn, styles.chipDanger]} onPress={this.cancelar}>
                        <Text style={styles.chipText}>Cancelar</Text>
                      </TouchableOpacity>
                      <TouchableOpacity style={[styles.chipBtn, styles.primary]} onPress={this.confirmar}>
                        <Text style={styles.chipText}>Confirmar</Text>
                      </TouchableOpacity>
                    </View>
                  )}
                </>
              )}
            </View>
          </View>

          {this.renderNomesRow()}

          {/* Cabeçalho da tabela */}
          <View style={styles.tableHeader}>
            <Text style={styles.headerText}>Pedido</Text>
            <Text style={styles.headerText}>Quant</Text>
            <Text style={styles.headerText}>Valor</Text>
          </View>

          {this.renderTabelaPedidos()}
          {this.renderResumoPagamento()}
        </ScrollView>

        {this.renderAlterarValorModal()}
        {this.renderBrindeModal()}
        {this.renderPagamentosModal()}{/* <<< novo */}

        {/* Modal unificado de pagamento */}
        <Modal
  visible={this.state.showPayModal}
  transparent
  animationType="fade"
  onRequestClose={this.fecharPayModal}
>
  <KeyboardAvoidingView
    style={styles.modalAvoider}
    behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    keyboardVerticalOffset={Platform.OS === 'ios' ? 64 : 24}
  >
    <Pressable style={styles.modalBackdrop} onPress={this.fecharPayModal} />
    <View style={styles.bigModal}>
      <Text style={styles.bigModalTitle}>Confirmar pagamento</Text>

      {/* Pílulas de método de pagamento */}
      <View style={styles.methodPillsRow}>
        {this.state.opcoesMetodoPag.map((m) => {
          const isSel = this.state.metodoPagSelecionado === m;
          return (
            <TouchableOpacity
              key={m}
              onPress={() => this.setState({ metodoPagSelecionado: m })}
              style={[styles.methodPill, isSel && styles.methodPillSelected]}
            >
              <Text style={[styles.methodPillText, isSel && styles.methodPillTextSelected]}>
                {m.toUpperCase()}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {/* Totais dinâmicos */}
      {(() => {
        const base = this.getModalBase();
        const comDez = this.state.aplicarDez ? base * 1.1 : base;
        const cx = this.parseMoney(this.state.caixinhaValor);
        const caixinha = cx > 0 ? cx : 0;
        const totalFinal = comDez + caixinha;

        return (
          <>
            <View style={styles.miniTotalRow}>
              <Text style={styles.miniTotalLabel}>Subtotal selecionado</Text>
              <Text style={styles.miniTotalValue}>R$ {base.toFixed(2)}</Text>
            </View>
            {this.state.aplicarDez && (
              <View style={styles.miniTotalRow}>
                <Text style={styles.miniTotalLabel}>10%</Text>
                <Text style={styles.miniTotalValue}>R$ {(comDez - base).toFixed(2)}</Text>
              </View>
            )}
            {caixinha !== 0 && (
              <View style={styles.miniTotalRow}>
                <Text style={styles.miniTotalLabel}>Caixinha</Text>
                <Text style={styles.miniTotalValue}>R$ {caixinha.toFixed(2)}</Text>
              </View>
            )}
            <View style={[styles.miniTotalRow, { marginTop: 12 }]}>
              <Text style={[styles.miniTotalLabel, { fontSize: 16 }]}>Total final</Text>
              <Text style={[styles.miniTotalValue, { fontSize: 24 }]}>R$ {totalFinal.toFixed(2)}</Text>
            </View>
          </>
        );
      })()}

      {/* Toggle 10% */}
      <View style={{ marginTop: 16, alignItems: 'flex-start' }}>
  <TouchableOpacity
    onPress={() => this.setState({ aplicarDez: !this.state.aplicarDez })}
    style={[styles.miniBtn, this.state.aplicarDez ? styles.miniBtnPrimary : styles.miniBtnGhost]}
  >
    <Text style={this.state.aplicarDez ? styles.miniBtnPrimaryText : styles.miniBtnGhostText}>
      {this.state.aplicarDez ? 'Tirar 10%' : 'Adicionar 10%'}
    </Text>
  </TouchableOpacity>
</View>


      {/* Caixinha */}
      <Text style={[styles.miniTotalLabel, { marginTop: 16 }]}>Caixinha (opcional)</Text>
      <TextInput
        keyboardType="numeric"
        placeholder="0,00"
        placeholderTextColor="#999"
        onChangeText={(v) => this.setState({ caixinhaValor: v })}
        value={this.state.caixinhaValor}
        style={[styles.miniInput, { marginBottom: 16 }]}
      />

      {/* Ações */}
      <View style={styles.miniActions}>
        <TouchableOpacity
          style={[styles.miniBtn, styles.miniBtnGhost]}
          onPress={this.fecharPayModal}
          disabled={this.state.pagandoLoading}
        >
          <Text style={styles.miniBtnGhostText}>Cancelar</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.miniBtn, styles.miniBtnPrimary]}
          onPress={this.confirmarPagamentoComEscolhas}
          disabled={this.state.pagandoLoading}
        >
          <Text style={styles.miniBtnPrimaryText}>
            {this.state.pagandoLoading ? 'Enviando...' : 'Confirmar'}
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  </KeyboardAvoidingView>
</Modal>

      </View>
    );
  }
}

// ====== styles ======
const styles = StyleSheet.create({
  // layout base
  container: { flex: 1, backgroundColor: '#fff', paddingHorizontal: 16, paddingTop: 12 },
  title: {
    flexGrow: 1,
    flexShrink: 1,
    marginRight: 12,
    fontSize: 18,
    fontWeight: '700',
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  headerControls: {
    flexDirection: 'row',
    alignItems: 'center',
    flexShrink: 0,
    marginLeft: 8,
  },
  navGroup: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  navBtn: {
    width: 36, height: 36, borderRadius: 8, backgroundColor: '#2f6fdf',
    alignItems: 'center', justifyContent: 'center', elevation: 2, marginHorizontal: 4,
  },
  navBtnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  ordemText: { width: 26, textAlign: 'center', fontWeight: '700', color: '#1f2d3d' },
  inlineActions: { flexDirection: 'row', alignItems: 'center', flexWrap: 'nowrap' },

  // chips/botões
  chipBtn: { paddingVertical: 8, paddingHorizontal: 12, borderRadius: 10, alignItems: 'center', justifyContent: 'center', marginHorizontal: 4 },
  chipText: { color: '#fff', fontWeight: '700' },
  chipNeutral: { backgroundColor: '#6b7280' },
  chipWarn: { backgroundColor: '#f59e0b' },
  chipDanger: { backgroundColor: '#ef4444' },
  primary: { backgroundColor: '#17315c' },

  // tabela
  tableHeader: {
    flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 10,
    borderBottomWidth: 1, borderBottomColor: '#ddd', marginBottom: 8, backgroundColor: '#f7f7f7',
  },
  headerText: { flex: 1, fontSize: 16, fontWeight: '700', textAlign: 'center' },
  tableRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: '#eee' },
  itemText: { fontSize: 15, color: '#1f2d3d' },
  editControls: { flexDirection: 'row', marginLeft: 10 },
  miniSquare: {
    width: 36, height: 36, borderRadius: 8, alignItems: 'center', justifyContent: 'center', elevation: 2,
    shadowColor: '#000', shadowOpacity: 0.12, shadowOffset: { width: 0, height: 1 }, shadowRadius: 2, marginHorizontal: 4,
  },
  miniSquareText: { color: '#fff', fontWeight: '800', fontSize: 16 },
  danger: { backgroundColor: '#ef4444' },

  // resumo / pagamento
  summaryBox: { marginTop: 14, padding: 14, backgroundColor: '#f3f4f6', borderRadius: 12 },
  paymentRow: { flexDirection: 'row', justifyContent: 'space-between' },
  paymentBlock: { alignItems: 'center', flex: 1 },
  totalText: { fontSize: 12, fontWeight: '700', color: '#6b7280' },
  totalValue: { fontSize: 22, marginVertical: 6, color: '#111827' },
  parcialRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 12 },
  input: {
    height: 42, borderColor: '#d1d5db', borderWidth: 1, paddingHorizontal: 10, borderRadius: 8,
    flex: 1, backgroundColor: '#fff', marginRight: 8,
  },
  buttonRow: { flexDirection: 'row', justifyContent: 'space-between' },

  // FAB
  fab: {
    width: 44, height: 44, borderRadius: 22, backgroundColor: '#17315c',
    alignItems: 'center', justifyContent: 'center', marginLeft: 6, elevation: 3,
  },
  fabPlus: { color: '#fff', fontSize: 24, fontWeight: 'bold', lineHeight: 26 },

  // bottom sheet (opções)
  sheetBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.35)' },
  sheetContainer: {
    position: 'absolute',
    left: 12, right: 12,
    bottom: SHEET_BOTTOM,
    backgroundColor: '#fff',
    borderRadius: 16,
    paddingTop: 8, paddingBottom: 16, paddingHorizontal: 16,
    elevation: 12,
    shadowColor: '#000', shadowOffset: { width: 0, height: -2 }, shadowOpacity: 0.15, shadowRadius: 6,
  },
  sheetHandle: { alignSelf: 'center', width: 42, height: 4, borderRadius: 2, backgroundColor: '#d8dbe2', marginBottom: 8 },
  sheetTitle: { fontSize: 16, fontWeight: '700', color: '#2b3a4a', marginBottom: 8, textAlign: 'center' },
  sheetItem: { paddingVertical: 12, paddingHorizontal: 8, borderRadius: 8 },
  sheetItemText: { fontSize: 16, color: '#1f2d3d', textAlign: 'center' },
  sheetCancel: { marginTop: 8, paddingVertical: 12, borderRadius: 10, backgroundColor: '#f3f4f6' },
  sheetCancelText: { textAlign: 'center', fontSize: 15, color: '#374151', fontWeight: '600' },

  // mini-modais base
  modalAvoider: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  modalBackdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(0,0,0,0.5)' },
  miniModal: {
    width: 300,
    padding: 20,
    backgroundColor: 'white',
    borderRadius: 12,
    elevation: 5,
    shadowColor: '#000',
    shadowOpacity: 0.3,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
  },
  miniModalTitle: { fontSize: 17, fontWeight: '700', color: '#1f2d3d', marginBottom: 10, textAlign: 'center' },
  miniInput: {
    height: 42, borderWidth: 1, borderColor: '#d1d5db', borderRadius: 8, paddingHorizontal: 10, backgroundColor: '#fbfbfb', fontSize: 16,
  },
  miniActions: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 14 },
  miniBtn: {
    paddingVertical: 12,
    paddingHorizontal: 18,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 6,
  },
  miniBtnGhost: {
    backgroundColor: '#f3f4f6', // cinza claro
  },
  miniBtnGhostText: {
    color: '#374151',
    fontWeight: '700',
  },
  miniBtnPrimary: {
    backgroundColor: '#17315c',
  },
  miniBtnPrimaryText: {
    color: '#fff',
    fontWeight: '700',
  },
  
  // sugestões do brinde
  sugestoesBox: { maxHeight: 180, marginTop: 10, borderWidth: 1, borderColor: '#e5e7eb', borderRadius: 8, overflow: 'hidden' },
  sugestaoItem: { paddingVertical: 10, paddingHorizontal: 12, borderBottomWidth: 1, borderColor: '#f0f0f0', backgroundColor: '#fff' },
  sugestaoText: { fontSize: 15.5, color: '#222' },

  // nomes
  nomeRow: { flexDirection: 'row', marginVertical: 10, flexWrap: 'wrap' },
  nomeButtonWrapper: { marginHorizontal: 5, marginBottom: 6 },
  sectionTitle: { fontSize: 13, fontWeight: '700', color: '#6b7280', marginBottom: 6, marginTop: 4 },

  // controles do modo pagar por item
  payControls: { flexDirection: 'row', alignItems: 'center', marginLeft: 8, gap: 6 },
  payBtn: { width: 32, height: 32, borderRadius: 8, alignItems: 'center', justifyContent: 'center', elevation: 2 },
  payMinus: { backgroundColor: '#ef4444' },
  payPlus: { backgroundColor: '#17315c' },
  payBtnText: { color: '#fff', fontWeight: '800', fontSize: 16 },
  payQtyText: { minWidth: 18, textAlign: 'center', fontWeight: '700', color: '#111827' },

  // pílulas de método + totais do modal
  methodPillsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 4, marginBottom: 6 },
  methodPill: { paddingVertical: 8, paddingHorizontal: 12, borderRadius: 999, borderWidth: 1, borderColor: '#d1d5db', backgroundColor: '#fff', marginRight: 8, marginBottom: 8 },
  methodPillSelected: { backgroundColor: '#17315c', borderColor: '#17315c' },
  methodPillText: { color: '#374151', fontWeight: '700' },
  methodPillTextSelected: { color: '#fff', fontWeight: '800' },

  miniTotalLabel: { fontSize: 14, color: '#374151', fontWeight: '700' },
  miniTotalValue: { fontSize: 20, color: '#111827', fontWeight: '800' },
  bigModal: {
    width: '90%',
    maxWidth: 400,
    padding: 24,
    backgroundColor: 'white',
    borderRadius: 14,
    elevation: 6,
    shadowColor: '#000',
    shadowOpacity: 0.25,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 3 },
  },
  bigModalTitle: {
    fontSize: 19,
    fontWeight: '700',
    color: '#1f2d3d',
    marginBottom: 18,
    textAlign: 'center',
  },
  miniTotalRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 10,   // espaçamento maior entre blocos
  },
  bigModal: {
    width: '90%',
    maxWidth: 420,
    padding: 22,
    backgroundColor: 'white',
    borderRadius: 14,
    elevation: 6,
    shadowColor: '#000',
    shadowOpacity: 0.25,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 3 },
  },
  bigModalTitle: {
    fontSize: 19,
    fontWeight: '700',
    color: '#1f2d3d',
    marginBottom: 14,
    textAlign: 'center',
  },
  centerBox: { alignItems: 'center', justifyContent: 'center', paddingVertical: 24 },
  
  paymentItem: {
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  paymentMainRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  paymentLeft: { flexShrink: 1, paddingRight: 12 },
  paymentValue: { fontSize: 18, fontWeight: '800', color: '#111827' },
  paymentMeta: { marginTop: 2, color: '#374151', fontWeight: '600' },
  paymentMetaMuted: { marginTop: 2, color: '#9CA3AF', fontSize: 12 },
  
  paymentDeleteBtn: {
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 8,
    backgroundColor: '#ef4444',
  },
  paymentDeleteText: { color: '#fff', fontWeight: '800' },
  itemOptionsText: {
    fontSize: 12,
    color: '#6b7280',
    marginTop: 2,
  },
  itemExtrasText: {
    fontSize: 12.5,
    color: '#6b7280',
    marginTop: 2,
  },  
  
});

export default ComandaScreen;
