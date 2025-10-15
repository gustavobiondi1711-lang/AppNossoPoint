import { View, TextInput, Button, FlatList, StyleSheet, TouchableOpacity, Text, ScrollView, RefreshControl } from 'react-native';
import React from 'react';
import io from 'socket.io-client';
import { API_URL } from "./url";
import { UserContext } from '../UserContext';
import { getSocket } from '../socket';

export default class VerComandas extends React.Component {
  static contextType = UserContext;
  constructor(props) {
    super(props);
    this.state = {
      fcomanda: '',
      dataGeralAberto: [],
      dataGeralFechado: [],
      dataAberto: [],
      dataFechado: [],
      username: '',
      comandas: '',
      refreshing: false, // Estado para o pull-to-refresh
    };
    this.socket = null;
  }

  componentDidMount() {
    const { user } = this.context || {};
    this.setState({ username: user?.username || "" });
    this.socket = getSocket();

    // registra listener com referência estável
    this.socket.on("respostaComandas", this.handleRespostaComandas);

    // primeira carga
    this.emitGetComandas();
  }

  componentWillUnmount() {
    if (this.socket) {
      this.socket.off("respostaComandas", this.handleRespostaComandas);
    }
    if (this.refreshTimeout) {
      clearTimeout(this.refreshTimeout);
    }
  }

  // ------- handlers -------
  handleRespostaComandas = (dados) => {
    // garante que só finaliza refreshing ao receber dados
    this.setState({
      dataGeralAberto: dados?.dados_comandaAberta ?? [],
      dataGeralFechado: dados?.dados_comandaFechada ?? [],
      dataAberto: dados?.dados_comandaAberta ?? [],
      dataFechado: dados?.dados_comandaFechada ?? [],
      refreshing: false,
    });
  };

  emitGetComandas = () => {
    this.socket.emit("getComandas", false);
  };

  // ------- refresh -------
  refreshData = () => {
    this.setState({ refreshing: true }, () => {
      this.emitGetComandas();

      // Fallback: se o backend não responder, não deixar o spinner infinito
      if (this.refreshTimeout) clearTimeout(this.refreshTimeout);
      this.refreshTimeout = setTimeout(() => {
        this.setState({ refreshing: false });
      }, 10000); // 10s
    });
  };

  getCardapio = (item, ordem) => {
    const { username } = this.state;
    this.socket.emit('get_cardapio', { fcomanda: item.comanda, ordem: ordem });

    this.socket.once('preco', (data) => {
      this.props.navigation.navigate('Comanda', {
        data: data.dados,
        fcomanda: item.comanda,
        preco: data.preco_a_pagar,
        preco_total: data.preco_total,
        preco_pago: data.preco_pago,
        username: username,
        nomes: data.nomes,
        ordem: ordem,
      });
      this.setState({ fcomanda: '' });
    });
  };

  searchcomanda = (comandas) => {
    if (comandas && (!!this.state.dataGeralAberto || !!this.state.dataGeralFechado)) {
      const data_filtradoAberto = this.state.dataGeralAberto.filter((item) => item.comanda.startsWith(comandas.toLowerCase()));
      const data_filtradoFechado = this.state.dataGeralFechado.filter((item) => item.comanda.startsWith(comandas.toLowerCase()));
      this.setState({ comandas, dataAberto: data_filtradoAberto, dataFechado: data_filtradoFechado });
    } else {
      this.setState({ comandas, dataAberto: this.state.dataGeralAberto || [], dataFechado: this.state.dataGeralFechado || [] });
    }
  };

  render() {
    const { dataAberto, dataFechado, refreshing } = this.state;

    return (
      <ScrollView
        contentContainerStyle={styles.container}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={this.refreshData} />
        }
      >
        <View style={styles.tableHeader}>
          <TextInput
            style={styles.inputcomanda}
            onChangeText={this.searchcomanda}
            value={this.state.comandas}
            placeholder="Pesquisa comanda..."
            placeholderTextColor="#999"
          />
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Comandas Abertas</Text>
          {dataAberto.length>0 ?(
            dataAberto.map((item, index) => (
              <TouchableOpacity key={index} onPress={() => this.getCardapio(item, 0)} style={styles.comandaButton}>
                <Text style={styles.comandaText}>Comanda: {item.comanda}</Text>
              </TouchableOpacity>
            ))
          ) : (
            <Text style={{ color: '#666' }}>Nenhuma comanda aberta.</Text>
          )
          }
        </View>

        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Comandas Fechadas</Text>
          {dataFechado.length >0 ? (
            dataFechado.map((item, index) => (
              <TouchableOpacity key={index+1*1000} onPress={() => this.getCardapio(item, item.ordem)} style={styles.comandaButtonClosed}>
                <Text style={styles.comandaText}>Comanda: {item.comanda}</Text>
              </TouchableOpacity>
            ))
          ) : (
            <Text style={{ color: '#666' }}>Nenhuma comanda fechada.</Text>
          )
          }
        </View>
      </ScrollView>
    );
  }
}

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
    padding: 20,
    backgroundColor: '#F5F5F5',
  },
  section: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 10,
    color: '#333',
  },
  comandaButton: {
    backgroundColor: '#00BFFF',
    padding: 15,
    borderRadius: 8,
    marginBottom: 10,
  },
  comandaButtonClosed: {
    backgroundColor: '#D32F2F',
    padding: 15,
    borderRadius: 8,
    marginBottom: 10,
  },
  comandaText: {
    fontSize: 16,
    color: '#FFF',
    textAlign: 'center',
  },
  tableHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 15,
    backgroundColor: '#f1f3f5',
    borderRadius: 12,
    marginBottom: 10,
    width: '95%',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 3,
    elevation: 5,
  },
  inputcomanda: {
    height: 45,
    borderColor: '#ced4da',
    borderWidth: 1,
    paddingHorizontal: 15,
    borderRadius: 8,
    backgroundColor: '#ffffff',
    flex: 1,
    fontSize: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
    outlineStyle: 'none',
  },
});
