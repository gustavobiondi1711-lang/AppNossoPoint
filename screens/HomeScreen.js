import React from 'react';
import { StyleSheet, View, Button, TextInput, FlatList, TouchableOpacity, Text,ScrollView,Pressable} from 'react-native';
import { Animated } from 'react-native';
import { UserContext } from '../UserContext'; // Import the context
import { API_URL } from "./url";
import { Keyboard } from 'react-native';
import debounce from 'lodash.debounce';
import { getSocket } from '../socket';
import NetInfo from "@react-native-community/netinfo";

// formata R$ de forma robusta no RN
const brl = (n) => {
  const v = Number(n || 0);
  const s = (isNaN(v) ? 0 : v).toFixed(2);
  return `R$ ${s.replace('.', ',')}`;
};


export default class HomeScreen extends React.Component {
  static contextType = UserContext;

  constructor(props) {
    super(props);
    this.state = {
      username:'',
      cargo:'',
      comand: '',
      pedido: '',
      extra: '',
      nome:'',
      data: [],
      dataFixo:[],
      pedido_filtrado: [],
      comanda_filtrada:[],
      comandaGeral:[],
      quantidadeSelecionada: [],
      pedidosSelecionados: [],
      extraSelecionados: [],
      nomeSelecionado:[],
      options:[],
      selecionadosByGroup:[],
      showPedido: false,
      showComandaPedido: false,
      showComanda:false,
      showQuantidade: false,
      showPedidoSelecionado: false,
      quantidade: 1,
      quantidadeRestanteMensagem: null,
      pedidoRestanteMensagem: null,
      showConfirmOrder: false,
      confirmMsg: 'Pedido enviado com sucesso!',
      isConnected: true,
      toastVariant: 'success',
      selectedUnitPrices: [],              // preço unitário (base + extras) por item adicionado
      opcoesSelecionadasPorItem: [],       // array de seleções por item (p/ render bonitinho)

    };
    this.processarPedido = debounce(this.processarPedido.bind(this), 200);
    this.socket = null;
    this._toastOpacity = new Animated.Value(0);
    this._toastTranslateY = new Animated.Value(-12);
    this._hideToastTimer = null;
    this._isMounted = false;
  }

  async componentDidMount() {
    this._isMounted = true;
    const { user } = this.context || {};
    this.setState({ username: user?.username || "" });
    if (user?.username) console.log(user.username);
  
    // 1) Monitor da rede do aparelho
    this._netinfoUnsub = NetInfo.addEventListener(this.handleNetInfoChange);
  
    // 2) Checagem inicial da rede
    try {
      const net = await NetInfo.fetch();
      this.setState({ isConnected: !!net.isConnected });
      if (!net.isConnected) {
        this.showConfirmToast('Sem internet no dispositivo.');
      }
    } catch {}
  
    // 3) Socket.io
    this.socket = getSocket();
  
    // listeners com referência estável (métodos da classe)
    this.socket.on("respostaCardapio", this.handleRespostaCardapio);
    this.socket.on("respostaComandas", this.handleRespostaComandas);
    this.socket.on("error", this.handleSocketError);
    this.socket.on("alerta_restantes", this.handleAlertaRestantes);
    this.socket.on("quantidade_insuficiente", this.handleQuantidadeInsuficiente);
    this.socket.on("connect", this.handleSocketConnect);
    this.socket.on("disconnect", this.handleSocketDisconnect);
  
    // 4) Primeiras cargas: só dispara se tiver rede (evita chamadas inúteis)
    if (this.state.isConnected) {
      this.socket.emit("getCardapio", false);
      this.socket.emit("getComandas", false);
    } else {
      this.showConfirmToast('Sem internet. Tentando novamente quando voltar.');
    }
  }
  

  componentWillUnmount() {
    this._isMounted = false;
    if (this._hideToastTimer) clearTimeout(this._hideToastTimer);
    // remover listener do NetInfo
    if (this._netinfoUnsub) {
      this._netinfoUnsub();
      this._netinfoUnsub = null;
    }
  
    if (this.socket) {
      this.socket.off("respostaCardapio", this.handleRespostaCardapio);
      this.socket.off("respostaComandas", this.handleRespostaComandas);
      this.socket.off("error", this.handleSocketError);
      this.socket.off("alerta_restantes", this.handleAlertaRestantes);
      this.socket.off("quantidade_insuficiente", this.handleQuantidadeInsuficiente);
      this.socket.off("connect", this.handleSocketConnect);
      this.socket.off("disconnect", this.handleSocketDisconnect);
      // não faz disconnect() se o socket é global/compartilhado
    }
  }
  
  // -------- handlers estáveis --------
  handleRespostaCardapio = (data) => {
    if (data?.dataCardapio) {
      this.setState({
        pedido_filtrado: data.dataCardapio,
        dataFixo: data.dataCardapio,
      });
    } else {
      console.warn("Resposta de cardápio inválida:", data);
    }
  };
  // cole no topo da classe (helper simples)


  handleComandaFocus = () => {
    this.setState({ showComandaPedido: !!(this.state.comand && this.state.comand.trim()) });
  };
  
  handleComandaBlur = () => {
    // dá tempo do onPress da sugestão disparar antes de esconder
    setTimeout(() => this.setState({ showComandaPedido: false }), 0);
  };
  
  handlePedidoFocus = () => {
    this.setState({ showPedido: !!(this.state.pedido && this.state.pedido.trim()) });
  };
  
  handlePedidoBlur = () => {
    setTimeout(() => this.setState({ showPedido: false }), 0);
  };
  handleSocketConnect = () => {
    this.showConfirmToast('Conectado novamente!', 'success');
  };
  
  handleSocketDisconnect = () => {
    this.showConfirmToast('Sem conexão com o servidor.', 'error');
  };
  
  handleNetInfoChange = (state) => {
    const was = this.state.isConnected;
    const now = !!state.isConnected;
    if (was !== now) {
      this.setState({ isConnected: now });
      if (!now) {
        this.showConfirmToast('Sem internet no dispositivo.','error');
      } else {
        this.showConfirmToast('Internet restaurada.','success');
      }
    }
  };
  

  handleRespostaComandas = (data) => {
    if (data?.dados_comandaAberta) {
      this.setState({
        comanda_filtrada: data.dados_comandaAberta,
        comandaGeral: data.dados_comandaAberta,
      });
    }
  };

  handleSocketError = ({ message }) => {
    console.error("Erro do servidor:", message);
  };

  handleAlertaRestantes = (data) => {
    if (!data) return;
    this.setState({
      quantidadeRestanteMensagem: data.quantidade ?? 0,
      pedidoRestanteMensagem: data.item ?? "",
    });
  };

  handleQuantidadeInsuficiente = (data) => {
    const { user } = this.context || {};
    if (data?.erro) {
      this.setState({
        comand: "",
        pedido: "",
        extra: "",
        quantidade: 1,
        showQuantidade: false,
        showPedidoSelecionado: false,
      });
      alert("Quantidade Insuficiente");
      return;
    }

    const { comand, pedido, quantidade, extra } = this.state;
    const currentTime = this.getCurrentTime();
    this.socket.emit("insert_order", {
      comanda: comand,
      pedidosSelecionados: [pedido],
      quantidadeSelecionada: [quantidade],
      extraSelecionados: [extra],
      horario: currentTime,
      token_user: user?.token,
    });

    this.setState({ comand: "", pedido: "", quantidade: 1, extra: "" });
  };

  // util
  getCurrentTime = () => {
    const d = new Date();
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    return `${hh}:${mm}`;
  };
// helper pra normalizar só pra busca
normalize = (s) =>
  String(s || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');

  // limpa somente o estado da SELEÇÃO ATUAL (chips/opções do item em edição)
resetCurrentSelection = (extra = {}) => {
  this.setState({
    options: [],
    selecionadosByGroup: [],
    showQuantidade: false,
    ...extra, // permite sobrescrever algo quando quiser
  });
};


changeComanda = (comand) => {
  const base = Array.isArray(this.state.comandaGeral) ? this.state.comandaGeral : [];
  const raw = String(comand.toLowerCase() ?? '');    // mantém como o usuário digitou (com maiúsculas, espaços etc)
  const qNorm = this.normalize(raw);   // usado só para busca
  const words = qNorm.trim().split(/\s+/).filter(Boolean);

  // vazio → retorna tudo
  if (words.length === 0) {
    this.setState({
      comanda_filtrada: base,
      comand: raw,               // <<< aqui mostra o que o usuário digitou (sem mudar)
      showComandaPedido: false,
    });
    return;
  }

  const starts = [];
  const allWords = [];
  const includes = [];

  for (let i = 0; i < base.length; i++) {
    const it = base[i];
    const nameNorm = this.normalize(it?.comanda); // nome normalizado só pra comparar
    if (!nameNorm) continue;

    // começa com QUALQUER palavra
    let matched = false;
    for (const w of words) {
      if (nameNorm.startsWith(w)) { starts.push(it); matched = true; break; }
    }
    if (matched) continue;

    // contém TODAS as palavras
    if (words.length > 1 && words.every((w) => nameNorm.includes(w))) {
      allWords.push(it);
      continue;
    }

    // contém QUALQUER palavra
    for (const w of words) {
      if (nameNorm.includes(w)) { includes.push(it); break; }
    }
  }

  // junta e remove duplicados
  const seen = new Set();
  const comanda_filtrada = [];
  for (const bucket of [starts, allWords, includes]) {
    for (const it of bucket) {
      const key = it?.id ?? it?.comanda;
      if (!seen.has(key)) {
        seen.add(key);
        comanda_filtrada.push(it);
      }
    }
  }

  this.setState({
    comanda_filtrada,
    comand: raw,               // <<< mantém o digitado com maiúscula e espaços
    showComandaPedido: true,
  });
};
  
showConfirmToast = (msg = 'Tudo certo!', variant = 'success') => {
  if (!this._isMounted || !this._toastOpacity || !this._toastTranslateY) return;

  this.setState({ showConfirmOrder: true, confirmMsg: msg, toastVariant: variant }, () => {
    Animated.parallel([
      Animated.timing(this._toastOpacity, { toValue: 1, duration: 180, useNativeDriver: true }),
      Animated.timing(this._toastTranslateY, { toValue: 0, duration: 180, useNativeDriver: true }),
    ]).start(() => {
      if (this._hideToastTimer) clearTimeout(this._hideToastTimer);
      this._hideToastTimer = setTimeout(() => {
        if (this._isMounted) this.hideConfirmToast();
      }, 2000);
    });
  });
};


hideConfirmToast = () => {
  if (!this._isMounted || !this._toastOpacity || !this._toastTranslateY) return;
  Animated.parallel([
    Animated.timing(this._toastOpacity, {
      toValue: 0,
      duration: 160,
      useNativeDriver: true,
    }),
    Animated.timing(this._toastTranslateY, {
      toValue: -12,
      duration: 160,
      useNativeDriver: true,
    }),
  ]).start(() => {
    if (this._isMounted) this.setState({ showConfirmOrder: false });
  });
};




  changePedido = (pedid) => {
    const pedido = String(pedid).toLowerCase();
    this.resetCurrentSelection();
    this.setState({
      pedido,
      showPedido: !!pedido,
    });

    this.processarPedido(pedido);
  }

  processarPedido(pedido) {
    const base = Array.isArray(this.state.dataFixo) ? this.state.dataFixo : [];
  
    // vazio → volta tudo
    const raw = String(pedido || '');
    if (!raw) {
      this.setState({ pedido_filtrado: [], showPedido: false });
      return;
    }
  
    // busca por ID com prefixo "."
    if (raw[0] === '.' && raw.length > 1) {
      const id = raw.slice(1).trim();
      const result = base.filter(it => String(it && it.id) === id);
      this.setState({ pedido_filtrado: result });
      return;
    }
  
    // busca por texto: prioridade startsWith > todasPalavras > includes
    const q = raw.toLowerCase().trim();
    if (!q) {
      this.setState({ pedido_filtrado: base });
      return;
    }
    const words = q.split(/\s+/).filter(Boolean);
  
    const starts = [];
    const allWords = [];
    const includes = [];
    
    for (let i = 0; i < base.length; i++) {
      const it = base[i];
      const name = String(it && it.item || '').toLowerCase();
      if (!name) continue;
  
      // começa com QUALQUER palavra
      let matched = false;
      for (let w of words) {
        if (name.startsWith(w)) { starts.push(it); matched = true; break; }
      }
      if (matched) continue;
  
      // contém TODAS as palavras (ordem livre)
      if (words.length > 1 && words.every(w => name.includes(w))) {
        allWords.push(it);
        continue;
      }
  
      // contém QUALQUER palavra
      for (let w of words) {
        if (name.includes(w)) { includes.push(it); break; }
      }
    }
  
    const result = starts.concat(allWords, includes);
    this.setState({ pedido_filtrado: result, showPedido: !!pedido });
  }
  
    
  getCurrentTime = () => new Date().toTimeString().slice(0, 5);

  


  verificarExistenciaPedidos(pedido){
    if (!!pedido){
    console.log('entrou verifExisPedi')
    console.log(pedido)
    const pedidExist = this.state.dataFixo.filter(item=>item.item==pedido)
    console.log(pedidExist)
    
    if (pedidExist.length>0){
    return true
    }
    else return false
  }
  
  else return true
  }
  
  sendData = async () => {
    const net = await NetInfo.fetch();
    if (!net.isConnected) {
      this.showConfirmToast('Sem internet. Tente novamente.','error');
      return;
    }
    if (!this.socket || !this.socket.connected) {
      this.showConfirmToast('Sem conexão com o servidor. Aguarde reconexão.','error');
      return;
    }

    const pedido = this.state.pedido.trim()
    const {user} = this.context
    if(this.verificarExistenciaPedidos(pedido)){
      
    const comand = this.state.comand.trim()
    const { nome,nomeSelecionado, pedidosSelecionados, quantidadeSelecionada, extraSelecionados, quantidade, extra, username,options,selecionados} = this.state;
    const currentTime = this.getCurrentTime();
    console.log(nomeSelecionado)
    
    
    if(!comand){
      alert("Digite a comanda");
    }
    else if (!pedido && !pedidosSelecionados){
      alert('Digite o pedido')
    }
    if (comand && pedidosSelecionados.length && quantidadeSelecionada.length) {
      
  
      // Encontra os índices com quantidade 0
      const indicesValidos = [];
      quantidadeSelecionada.forEach((q, i) => {
        if (q > 0) indicesValidos.push(i);
      });
      const NovasSelecoes = indicesValidos.map(i => this.state.opcoesSelecionadasPorItem[i] || []);

      const NovosPedidos=[]
      pedidosSelecionados.map((p,i)=>{
        for (let j=0;j<indicesValidos.length;j++){
          if (indicesValidos[j]===i){
            NovosPedidos.push(p)
          }
        }
      })
      const NovasQuantidades=[]
      quantidadeSelecionada.map((p,i)=>{
        for (let j=0;j<indicesValidos.length;j++){
          if (indicesValidos[j]===i){
            NovasQuantidades.push(p)
          }
        }
      })
      const NovosExtras=[]
      extraSelecionados.map((p,i)=>{
        for (let j=0;j<indicesValidos.length;j++){
          if (indicesValidos[j]===i){
            NovosExtras.push(p)
          }
        }
      })
      const NovosNomes=[]
      nomeSelecionado.map((p,i)=>{
        for (let j=0;j<indicesValidos.length;j++){
          if (indicesValidos[j]===i){
            NovosNomes.push(p)
          }
        }
      })
      
      this.socket.emit('insert_order', { 
        comanda: comand, 
        pedidosSelecionados:NovosPedidos, 
        quantidadeSelecionada:NovasQuantidades,
        extraSelecionados:NovosExtras,
        nomeSelecionado:NovosNomes,
        horario: currentTime,
        username:username,
        opcoesSelecionadas: NovasSelecoes,
        token_user:user.token
      });
      this.showConfirmToast('Enviado ✅', 'success' );
      this.setState({
        // inputs
        comand: '',
        pedido: '',
        extra: '',
        nome: '',
        // carrinho
        pedidosSelecionados: [],
        quantidadeSelecionada: [],
        extraSelecionados: [],
        nomeSelecionado: [],
        opcoesSelecionadasPorItem: [],
        selectedUnitPrices: [],
        // UI
        showPedidoSelecionado: false,
        showPedido: false,
        showComandaPedido: false,
        comanda_filtrada: [],
        comanda_filtrada_abrir: [],
        quantidade: 1,
        showQuantidade: false,
        showComanda: false,
        // seleção atual (chips)
        options: [],
        selecionadosByGroup: [],
      });
      
    } else if (comand && pedido && quantidade) {
      // valida obrigatório antes do fetch (quando há opções na tela)
      if ((this.state.options || []).length) {
        const { ok, msg } = this.validateRequiredGroups();
        if (!ok) { this.showConfirmToast(msg || 'Seleção incompleta.', 'warning'); return; }
      }
      fetch(`${API_URL}/verificar_quantidade`, {  
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            item: pedido,
            quantidade: quantidade
        })
    })
    .then(response => response.json())
    .then(data => {
      
      if (data.erro) {
        console.log(data)
        this.setState({
          comand: '',
          pedido: '',
          quantidade: 1,
          extra: '',
          nome: '',
          showComandaPedido: false,
          showPedidoSelecionado: false,
          showPedido: false,
          showQuantidade: false,
          // seleção atual:
          options: [],
          selecionadosByGroup: [],
          // auxiliares do carrinho também zeram porque só havia 1 item:
          opcoesSelecionadasPorItem: [],
          selectedUnitPrices: [],
        });
        
        const quantidade = data.quantidade
        const quantidadeRestante = 'quantidade estoque insuficiente. Restam apenas '+String(quantidade)
        alert(quantidadeRestante)
        ;
      } else {
        const {nomeSelecionado, quantidade, extra,username,nome,selecionados} = this.state;
        
        const quantidadeR = data.quantidade
        const novaQ = parseFloat(quantidadeR)-quantidade
        if (novaQ){
          const alerta = 'ATENCAO RESTAM APENAS '+String(novaQ)+'\nRECOMENDADO REPOR ESTOQUE!'
          alert(alerta)
        }

        const currentTime = this.getCurrentTime();
        this.socket.emit('insert_order', { 
          comanda: comand, 
          pedidosSelecionados: [pedido], 
          quantidadeSelecionada: [quantidade],
          extraSelecionados: [extra],
          nomeSelecionado:[nome],
          horario: currentTime,
          comanda_filtrada:[],
          comanda_filtrada_abrir:[],
          username:username,
          opcoesSelecionadas: [ this.buildSelectionFromState() ],
          token_user:user.token
        });
        this.showConfirmToast('Enviado ✅','success' );

        this.setState({
          comand: '',
          pedido: '',
          quantidade: 1,
          extra: '',
          nome: '',
          showComandaPedido: false,
          showPedidoSelecionado: false,
          showPedido: false,
          showQuantidade: false,
          // seleção atual:
          options: [],
          selecionadosByGroup: [],
          // auxiliares do carrinho também zeram porque só havia 1 item:
          opcoesSelecionadasPorItem: [],
          selectedUnitPrices: [],
        });
        
      }
    
    })
    .catch(error => console.error('Erro ao adicionar pedido:', error));
    }
    else {
      console.warn('Por favor, preencha todos os campos.');
    }
  }
  else{
    alert('Pedido Inexistente')
  }
  };
  // Normaliza/garante a forma do array de grupos recebido do cardápio
normalizeGroups = (raw) => {
  let groups = [];
  try {
    groups = typeof raw === 'string' ? JSON.parse(raw) : raw;
  } catch {
    groups = [];
  }
  if (!Array.isArray(groups)) groups = [];

  return groups.map(g => {
    const nome = g?.nome ?? g?.Nome ?? 'Opções';
    const ids = g?.ids ?? '';
    const max_selected = Number(g?.max_selected ?? 1) || 1;
    const obrigatorio = !!(g?.obrigatorio || g?.Obrigatorio);
    let options = g?.options ?? g?.opcoes ?? [];

    if (!Array.isArray(options)) options = [];
    options = options.map(o => {
      if (typeof o === 'string') return { nome: o, valor_extra: 0 };
      return {
        nome: o?.nome ?? String(o ?? ''),
        valor_extra: Number(o?.valor_extra ?? 0) || 0,
        esgotado: !!o?.esgotado,

      };
    });

    return { nome, ids, options, max_selected, obrigatorio }
  });
};

// retorna true/false e uma mensagem (se houver erro)
validateRequiredGroups = () => {
  const { options, selecionadosByGroup } = this.state;
  for (let i = 0; i < (options || []).length; i++) {
    const g = options[i];
    if (!g) continue;
    if (g.obrigatorio) {
      const sel = selecionadosByGroup[i] || [];
      // considera "obr." atendido se houver pelo menos uma opção selecionada
      if (!sel.length) {
        return { ok: false, msg: `Selecione ao menos 1 opção em "${g.nome}".` };
      }
    }
  }
  return { ok: true };
};

// soma dos extras com base na seleção atual (em memória)
computeExtrasFromSelection = () => {
  const selection = this.buildSelectionFromState(); // já existente
  let sum = 0;
  for (const g of selection) {
    for (const o of g.options || []) {
      sum += Number(o.valor_extra || 0);
    }
  }
  return sum;
};

// encontra o preço base do item atual digitado (ou selecionado)
getItemBasePrice = (itemName) => {
  const base = Array.isArray(this.state.dataFixo) ? this.state.dataFixo : [];
  const found = base.find(it => String(it.item || '').toLowerCase() === String(itemName || '').toLowerCase());
  const preco = found ? Number(found.preco || 0) : 0;
  return isNaN(preco) ? 0 : preco;
};

// faz um "resumo" de seleção p/ exibir no card do item adicionado
summarizeSelection = (selGroups = []) => {
  // selGroups: [{nome, options:[{nome, valor_extra}]}...]
  return selGroups.map(g => {
    const itens = (g.options || []).map(o => o.valor_extra ? `${o.nome} (+${brl(o.valor_extra)})` : o.nome);
    return `${g.nome}: ${itens.join(', ') || '—'}`;
  }).join(' • ');
};


// Enforce do max_selected por grupo
toggleOption = (groupIndex, optionName) => {
  this.setState(prev => {
    const selecionadosByGroup = [...prev.selecionadosByGroup];
    const selected = [...(selecionadosByGroup[groupIndex] || [])];
    const group = prev.options[groupIndex];
    if (!group) return null;

   // Bloqueia clique em opção esgotada
   const opt = (group.options || []).find(o => o.nome === optionName);
   if (opt && opt.esgotado) {
     // opcional: dar um feedback
     this.showConfirmToast('Opção esgotada', 'warning');
     return null;
   }

    const maxSel = Number(group.max_selected || 1);
    const already = selected.includes(optionName);

    if (already) {
      // Se já estava selecionada → desseleciona
      selecionadosByGroup[groupIndex] = selected.filter(n => n !== optionName);
    } else {
      // Se ainda não estava → adiciona
      if (selected.length >= maxSel) {
        // remove a mais antiga (primeiro da lista)
        selected.shift();
      }
      selected.push(optionName);
      selecionadosByGroup[groupIndex] = selected;
    }

    return { selecionadosByGroup };
  });
};


// Constrói a seleção estruturada para envio ao backend
buildSelectionFromState = () => {
  const { options, selecionadosByGroup } = this.state;
  if (!options || !options.length) return [];  // 🔑 nada selecionável

  return options.map((g, idx) => {
    const escolhidos = new Set(selecionadosByGroup[idx] || []);
    const opts = g.options
      .filter(o => escolhidos.has(o.nome))
      .map(o => ({ nome: o.nome, valor_extra: Number(o.valor_extra) || 0 }));
    return {
      nome: g.nome,
      ids: g.ids ?? '',
      options: opts,
      max_selected: Number(g.max_selected || 1),
    };
  }).filter(g => g.options.length > 0);
};


  pagarParcial = () => {
    const { valor_pago, fcomanda, preco } = this.state;
    const valorNum = parseFloat(valor_pago);
    if (!isNaN(valorNum) && valorNum > 0 && valorNum <= preco) {
      this.socket.emit('pagar_parcial', { valor_pago: valorNum, fcomanda });
      this.setState((prevState) => ({ preco: prevState.preco - valorNum, valor_pago: '' }));
    } else {
      console.warn('Insira um valor válido para pagamento parcial.');
    }
  };

  selecionarPedido = (pedid, id) => {
    const pedido = pedid.trim();
    const row = (this.state.dataFixo || []).find(r => String(r.id) == String(id))
             || (this.state.dataFixo || []).find(r => String(r.item || '').trim().toLowerCase() === pedido.toLowerCase());
    const groups = this.normalizeGroups(row?.opcoes);
  
    this.setState({
      pedido,
      pedido_filtrado: [],
      showQuantidade: true,
      options: groups,
      selecionadosByGroup: groups.map(() => []),
    });
  };
  

  
  selecionarComandaPedido =(comand) =>{
    this.setState({ comand, comanda_filtrada: [], showComandaPedido:false})
  }
  
  selecionarComanda =(fcomanda) =>{
    this.setState({ fcomanda, comanda_filtrada_abrir: [], showComanda:false})
  }

  aumentar_quantidade = () => this.setState((prevState) => ({ quantidade: prevState.quantidade + 1 }));
  diminuir_quantidade = () => this.setState((prevState) => ({ quantidade: Math.max(prevState.quantidade - 1, 1) }));
  mudar_quantidade = (quantidade) => this.setState({ quantidade: parseInt(quantidade) || 1 });
  
  adicionarPedido = () => {
    const pedido = this.state.pedido.trim();
    const { showQuantidade, quantidade } = this.state;
    
    if (showQuantidade) {
     // 1) valida grupos obrigatórios antes de consultar estoque
   const { ok, msg } = this.validateRequiredGroups();
   if (!ok) {
     this.showConfirmToast(msg || 'Seleção incompleta.', 'warning');
     return;
   }
      fetch(`${API_URL}/verificar_quantidade`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item: pedido, quantidade }),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.erro) {
            this.setState({
              quantidade: 1,
              showQuantidade: false,
              pedido: '',
              extra: '',
              nome: '',
              showPedidoSelecionado: false,
              showPedido: false,
              options: [],
              selecionadosByGroup: [],
            
            });
            const quantidade = data.quantidade;
            alert('Quantidade insuficiente. Restam apenas ' + String(quantidade));
          } else {
            const { pedido, quantidade, extra, nome } = this.state;
             // 2) monta seleção atual e calcula o preço unit (base + extras)
          const selection = this.buildSelectionFromState();  // [{nome, ids, options:[{nome, valor_extra}], max_selected}, ...]
          const extrasSum = this.computeExtrasFromSelection(); // soma dos valor_extra
          const basePrice = this.getItemBasePrice(pedido);
          const unitPrice = basePrice + extrasSum;
            const quantidadeR = data.quantidade;
            const novaQ = parseFloat(quantidadeR) - quantidade;
            if (novaQ) {
              alert(
                'ATENÇÃO: restam apenas ' +
                  String(novaQ) +
                  '\nRecomenda-se repor estoque!'
              );
            }
  
            this.setState((prev) => ({
              pedidosSelecionados: [...prev.pedidosSelecionados, pedido],
              quantidadeSelecionada: [...prev.quantidadeSelecionada, quantidade],
              extraSelecionados: extra
                ? [...prev.extraSelecionados, extra]
                : [...prev.extraSelecionados, ''],
              nomeSelecionado: nome
                ? [...prev.nomeSelecionado, nome]
                : [...prev.nomeSelecionado, ''],
                // guarda o preço unitário e a seleção (p/ render)
              selectedUnitPrices: [...prev.selectedUnitPrices, unitPrice],
              opcoesSelecionadasPorItem: [...prev.opcoesSelecionadasPorItem, selection],
              quantidade: 1,
              showQuantidade: false,
              pedido: '',
              extra: '',
              nome: '',
              showPedidoSelecionado: true,
              showPedido: false,
              options: [],
              selecionadosByGroup: [],
            }));
  
            
          }
        })
        .catch((error) => {
          console.error('Erro ao adicionar pedido:', error);
   
        });
    }
  };
  


  adicionarPedidoSelecionado = (index) => this.setState((prevState) => ({ quantidadeSelecionada: prevState.quantidadeSelecionada.map((q, i) => (i === index ? q + 1 : q)) }));
  removerPedidoSelecionado = (index)=> {
    this.setState((prevState)=>({
    quantidadeSelecionada:prevState.quantidadeSelecionada.map((q,i)=>(i===index ? q-1<0? 0:q-1 :q)),
    }))
  }
  renderConfirmToast() {
    if (!this.state.showConfirmOrder) return null;
    if (!this._toastOpacity || !this._toastTranslateY) return null;
  
    const { toastVariant } = this.state;
    const bg =
      toastVariant === 'error'   ? '#ef4444' : // red-500
      toastVariant === 'warning' ? '#f59e0b' : // amber-500
      toastVariant === 'info'    ? '#3b82f6' : // blue-500
                                   '#22c55e';  // green-500 (success)
  
    return (
      <Animated.View
        pointerEvents="none"
        style={{
          position: "absolute",
          top: 16,
          right: 16,
          zIndex: 999,
          opacity: this._toastOpacity,
          transform: [{ translateY: this._toastTranslateY }],
        }}
      >
        <View style={{
          backgroundColor: bg,
          paddingVertical: 10,
          paddingHorizontal: 14,
          borderRadius: 8,
          flexDirection: "row",
          alignItems: "center",
        }}>
          <View style={{
            width: 12, height: 12, borderRadius: 6,
            backgroundColor: 'rgba(255,255,255,0.9)', marginRight: 8
          }} />
          <Text style={{ color: "#fff", fontWeight: "700" }}>
            {this.state.confirmMsg}
          </Text>
        </View>
      </Animated.View>
    );
  }
  
  

    
  changeExtra = (extra) => this.setState({ extra });
  render() {


  return (
    <View style={styles.mainContainer}>
      {this.renderConfirmToast()}
      <ScrollView contentContainerStyle={styles.scrollContainer} keyboardShouldPersistTaps="handled">
        <View style={styles.innerContainer}>
          <View style={styles.inputRow}>
              <TextInput
                placeholder="Comanda"
                placeholderTextColor="#999"
                onChangeText={this.changeComanda}
                value={this.state.comand}
                style={styles.inputComanda}
                autoComplete="off"          // Android
                autoCorrect={false}         // Ambos
                spellCheck={false}          // iOS
                textContentType="none"      // iOS
                importantForAutofill="no"
                onFocus={this.handleComandaFocus}   // 👈
                onBlur={this.handleComandaBlur}     // 👈
              />
              <TextInput
                placeholder="Digite o pedido"
                placeholderTextColor="#999"
                onChangeText={this.changePedido}
                value={this.state.pedido}
                style={styles.inputPedido}
                autoComplete="off"          // Android
                autoCorrect={false}         // Ambos
                spellCheck={false}          // iOS
                textContentType="none"      // iOS
                importantForAutofill="no"
                onFocus={this.handlePedidoFocus}   // 👈
                onBlur={this.handlePedidoBlur}     // 👈
              />
            {this.state.showQuantidade && (
              <View style={styles.quantityRow}>
                <Button title="-" onPress={this.diminuir_quantidade} />
                <TextInput
                  style={styles.inputQuantidade}
                  value={String(this.state.quantidade)}
                  onChangeText={this.mudar_quantidade}
                  autoComplete="off"          // Android
                  autoCorrect={false}         // Ambos
                  spellCheck={false}          // iOS
                  textContentType="none"      // iOS
                  importantForAutofill="no"
                />
                <Button title="+" onPress={this.aumentar_quantidade} />
              </View>
            )}
          </View>
          {Array.isArray(this.state.options) && this.state.options.map((group, gIdx) => {
              const selecionados = new Set(this.state.selecionadosByGroup[gIdx] || []);
              const selCount = selecionados.size;
              const maxSel = Number(group.max_selected || 1);

              return (
                <View key={gIdx} style={styles.categoriaContainer}>
                  <View style={styles.categoriaHeader}>
                    <Text style={styles.categoriaTitle}>{group.nome} {group.obrigatorio ? ' *' : ''}</Text>
                    <Text style={styles.categoriaCounter}>{selCount}/{maxSel}</Text>
                  </View>

                  <View style={styles.optionGrid}>
                    {group.options.map((opt, oIdx) => {
                      const isSelected = selecionados.has(opt.nome);
                      const isDisabled = !!opt.esgotado;

                      const label = opt.valor_extra ? `${opt.nome} (+${brl(opt.valor_extra)})` : opt.nome;
                      return (
                        <TouchableOpacity
                          key={oIdx}
                          onPress={() => !isDisabled && this.toggleOption(gIdx, opt.nome)}
                          activeOpacity={0.8}
                          style={[
                            styles.optionChip,
                            isSelected && styles.optionChipSelected,
                            isDisabled && styles.optionChipDisabled,
                          ]}
                        >
                          <Text
                            style={[
                              styles.optionChipText,
                              isSelected && styles.optionChipTextSelected,
                              isDisabled && styles.optionChipTextDisabled,

                            ]}
                            numberOfLines={2}
                          >
                            {isDisabled ? `${label} (esgotado)` : label}
                          </Text>

                          <View
                            style={[
                              styles.optionDot,
                              isSelected && styles.optionDotSelected,
                              isDisabled && styles.optionDotDisabled,
                            ]}
                          />
                        </TouchableOpacity>
                      );
                    })}
                  </View>
                </View>
              );
            })}


            
            <View>
            {this.state.showComandaPedido && this.state.comanda_filtrada.map((item, index) => (
              <TouchableOpacity
                key={index}
                style={styles.comandaItem}
                onPress={() => this.selecionarComandaPedido(item.comanda)}
              >
                <Text style={styles.comandaText}>{item.comanda}</Text>
              </TouchableOpacity>
            ))}
           </View>
            <View>
            {this.state.showPedido && this.state.pedido_filtrado.map((item, index) => (

              index<5 &&(

              <Pressable
                key={index}
                style={styles.pedidoSelecionadoItem}
                onPress={() => {
                  Keyboard.dismiss();
                  this.selecionarPedido(item.item,item.id);
                }}
              >
                <Text style={styles.pedidoText}>{item.item}</Text>
              </Pressable>
              )
            ))}
            </View>
       

            <TextInput
              placeholder="Extra (opcional)"
              placeholderTextColor="#999"
              onChangeText={this.changeExtra}
              value={this.state.extra}
              style={styles.inputExtra}
            />

            <TextInput
              placeholder="Nome (opicional)"
              placeholderTextColor="#999"
              onChangeText={(nome) => this.setState({ nome })}
              value={this.state.nome}
              style={styles.inputNome}
              autoComplete="off"          // Android
              autoCorrect={false}         // Ambos
              spellCheck={false}          // iOS
              textContentType="none"      // iOS
              importantForAutofill="no"
            />

            <View style={styles.actionRow}>
              <Button title="Adicionar" onPress={this.adicionarPedido} />
              {(this.state.showPedidoSelecionado !== this.state.showPedido && !this.state.pedido) && (
                <Button title="Enviar pedido" onPress={this.sendData} />
              )}
            </View>
            {this.state.pedidosSelecionados.map((item, index) => {
  const qtd = this.state.quantidadeSelecionada[index] || 1;
  const unit = this.state.selectedUnitPrices[index] || 0;
  const resumo = this.summarizeSelection(this.state.opcoesSelecionadasPorItem[index] || []);
  const extraTxt = this.state.extraSelecionados[index] || '';

  return (
    <View key={index} style={styles.cartItemCard}>
      <View style={styles.cartItemHeader}>
        <Text style={styles.cartItemTitle}>{item}</Text>
        <Text style={styles.cartItemSubtitle}>unit: {brl(unit)}</Text>
      </View>

      <View style={styles.cartItemBody}>
        {!!resumo && <Text style={styles.cartItemLine}>Opções: {resumo}</Text>}
        {!!extraTxt && <Text style={styles.cartItemLine}>Extra: {extraTxt}</Text>}
      </View>

      <View style={styles.cartItemPriceRow}>
        <View style={styles.cartQtyControls}>
          <Button title="-" color="red" onPress={() => this.removerPedidoSelecionado(index)} />
          <Text>{qtd}</Text>
          <Button title="+" onPress={() => this.adicionarPedidoSelecionado(index)} />
        </View>
        <Text style={styles.cartItemTitle}>{brl(unit * qtd)}</Text>
      </View>
    </View>
  );
})}
          </View>
        </ScrollView>
      </View>
    );
  }
}

export const getCurrentTime = () => new Date().toTimeString().slice(0, 5);

const styles = StyleSheet.create({
  mainContainer: {
    flex: 1,
    padding: 20,
    backgroundColor: '#fff',
  },
  scrollContainer: {
    paddingBottom: 40,
  },
  innerContainer: {
    flexGrow: 1,
  },
  inputRow: {flexDirection:"row",},
  inputComanda: {
    borderColor: 'gray',
    borderWidth: 1,
    borderRadius:5,
    flexDirection:'row',
  },
  inputPedido: {
    flex: 2,
    height: 40,
    borderColor: 'gray',
    borderWidth: 1,
    borderRadius: 5,
    marginHorizontal:5,
  },
  quantityRow: {flexDirection:"row",},
  inputQuantidade: {
    height: 40,
    width: 30,
    borderColor: 'gray',
    borderWidth: 1,
    borderRadius: 5,
    textAlign: 'center',
    marginHorizontal: 3,
  },
  categoriaContainer: {
    marginTop: 10,
  },
  categoriaTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 5,
  },
  optionItem: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth:0.5,
    borderColor:"black",
    borderStyle:"solid",
    },
  optionText: {
    fontSize: 14,
  },
  optionCircle: {
    width: 20,
    height: 20,
    borderRadius: 10,
  },
  inputExtra: {
    height: 40,
    borderColor: 'gray',
    borderWidth: 1,
    borderRadius: 5,
    paddingHorizontal: 10,
    marginTop: 15,
  },
  comandaItem: {
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderBottomWidth: 1,
    borderColor: '#eee',
    backgroundColor: '#fff',
  },
  
  comandaText: {
    fontSize: 16,
    color: '#333',
  },
  
  pedidoSelecionadoItem: {
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderBottomWidth: 1,
    borderColor: '#eee',
    backgroundColor: '#fff',
    borderRadius: 6,
    marginVertical: 4,
    marginHorizontal: 8,
    elevation: 1, // sombra leve no Android
    shadowColor: '#000', // sombra leve no iOS
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
  },
  
  pedidoText: {
    fontSize: 16,
    color: '#333',
  },
  
  inputNome: {
    height: 40,
    borderColor: 'gray',
    borderWidth: 1,
    borderRadius: 5,
    paddingHorizontal: 10,
    marginVertical: 10,
  },
  actionRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginVertical: 10,
  },
  pedidoEditItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 10,
  },
  pedidoEditControls: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  categoriaHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  categoriaCounter: {
    fontSize: 12,
    color: '#6b7280',
  },
  
  // grade que “encaixa” os chips e quebra linha
  optionGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: 6,
  },
  
  // chip base
  optionChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 9999,
    borderWidth: 1,
    borderColor: '#e5e7eb',
    backgroundColor: '#f8fafc',
    marginRight: 8,
    marginBottom: 8,
    maxWidth: '100%',
    flexShrink: 1, // deixa o texto quebrar sem estourar
  },
  
  // chip selecionado
  optionChipSelected: {
    borderColor: '#16a34a',
    backgroundColor: '#ecfdf5',
  },
 optionChipDisabled: {
   opacity: 0.5,
   backgroundColor: '#f3f4f6',
 },
    
  
  optionChipText: {
    fontSize: 14,
    color: '#111827',
    flexShrink: 1,
  },
  optionChipTextSelected: {
    fontWeight: '600',
  },
  optionChipTextDisabled: {
       textDecorationLine: 'line-through',
       color: '#6b7280',
     },
  
  // bolinha de status no chip
  optionDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: '#d1d5db',
    marginLeft: 8,
  },
  optionDotSelected: {
    backgroundColor: '#16a34a',
  },
  optionDotDisabled: {
       backgroundColor: '#e5e7eb',
     },
         // ---- Cards dos itens adicionados ----
     cartItemCard: {
       borderWidth: 1,
       borderColor: '#e5e7eb',
       borderRadius: 12,
       padding: 10,
       marginVertical: 6,
       backgroundColor: '#ffffff',
       shadowColor: '#000',
       shadowOpacity: 0.06,
       shadowRadius: 4,
       shadowOffset: { width: 0, height: 2 },
       elevation: 2,
     },
     cartItemHeader: {
       flexDirection: 'row',
       alignItems: 'center',
       justifyContent: 'space-between',
       marginBottom: 6,
     },
     cartItemTitle: { fontSize: 15, fontWeight: '700', color: '#111827' },
     cartItemSubtitle: { fontSize: 12, color: '#6b7280' },
     cartItemBody: { marginTop: 4, gap: 4 },
     cartItemLine: { fontSize: 13, color: '#374151' },
     cartItemPriceRow: {
       flexDirection: 'row',
       alignItems: 'center',
       justifyContent: 'space-between',
       marginTop: 8,
     },
     cartQtyControls: { flexDirection: 'row', alignItems: 'center', gap: 10 },
    
  toastContainer: {
    backgroundColor: '#22c55e', // verde (tailwind emerald-500)
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderRadius: 8,
    flexDirection: 'row',
    alignItems: 'center',
  },
  toastText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 14,
    marginLeft: 8,
  },
  toastDot: {
    width: 16,
    height: 16,
    borderRadius: 8,
    backgroundColor: 'rgba(255,255,255,0.9)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  toastShadow: {
    // sombra cross-platform
    shadowColor: '#000',
    shadowOpacity: 0.25,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
});
