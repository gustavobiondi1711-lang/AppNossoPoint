import React from 'react';
import { View, FlatList, Text, StyleSheet, TextInput, Modal, TouchableOpacity, RefreshControl } from 'react-native';
import io from 'socket.io-client';
import { API_URL } from "./url";
import { UserContext } from '../UserContext';
import { getSocket } from '../socket';

export default class PedidosScreen extends React.Component {
  static contextType = UserContext;
  constructor(props) {
    super(props);
    this.state = {
      data: [],
      showEditar: false,
      pedidosAlterados: [],
      dados_antigos: [],
      showModal: false,
      pedidoModal: {},
      editable: false,
      refreshing: false, // Adicionado para gerenciar o estado de refresh
    };
    this.refreshData = this.refreshData.bind(this);
    this.socket = null;
  }

  componentDidMount() {
    this.socket = getSocket();

    // registra o listener UMA vez com referência estável
    this.socket.on("respostaPedidos", this.handleRespostaPedidos);

    // primeira carga
    this.refreshData();
  }

  componentWillUnmount() {
    if (this.socket) {
      this.socket.off("respostaPedidos", this.handleRespostaPedidos);
      // não desconectar o socket global aqui (singleton)
    }
    if (this.refreshTimeout) clearTimeout(this.refreshTimeout);
  }

  // ------- handler estável -------
  handleRespostaPedidos = (dados) => {
    if (!dados?.dataPedidos) {
      this.setState({ refreshing: false });
      return;
    }
    // copia + inverte para não mutar o array original vindo do servidor
    const arrayInvertido = [...dados.dataPedidos].reverse();
    this.setState({ data: arrayInvertido, refreshing: false });
  };

  // ------- apenas emite; não registra listeners aqui -------
  refreshData = () => {
    this.setState({ refreshing: true }, () => {
      this.socket.emit("getPedidos", false);

      // fallback: evita spinner infinito se não vier resposta
      if (this.refreshTimeout) clearTimeout(this.refreshTimeout);
      this.refreshTimeout = setTimeout(() => {
        this.setState({ refreshing: false });
      }, 10000); // 10s
    });
  };

  alterarPedido = (campo, valor) => {
    this.setState(prevState => ({
      pedidoModal: { ...prevState.pedidoModal, [campo]: valor },
    }));
  };

  abrirModal = (item) => {
    this.setState({ pedidoModal: item, showModal: true });
  };

  handleConfirmar = () => {
    const {user}=this.context;
    this.socket.emit('atualizar_pedidos', { pedidoAlterado: this.state.pedidoModal,usuario:user.username,token:user.token });
    this.setState({ editable: false, pedidoModal: {}, showModal: false });
  };

  render() {
    const { data, refreshing } = this.state;
    return (
      <View style={{ flex: 1 }}>
        <FlatList
          data={data}
          keyExtractor={(item, index) => index.toString()}
          renderItem={({ item }) => (
            <View style={styles.tableRow}>
              <TouchableOpacity
                onPress={() => this.abrirModal(item)}
                style={styles.itemContainer}
              >
                <Text style={styles.itemText}>
                  {item.quantidade} {item.pedido} ({item.comanda}) - {item.inicio}
                </Text>
              </TouchableOpacity>
            </View>
          )}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={this.refreshData} // Chama o método de atualização ao puxar para baixo
            />
          }
        />

       
        <Modal
          animationType="slide"
          transparent={true}
          visible={this.state.showModal}
          onRequestClose={() => this.setState({ showModal: false })}
        >
          <View style={styles.modalOverlay}>
            <View style={styles.modalContent}>
              
              {this.state.editable ? (
                <TouchableOpacity
                  style={[styles.EitButton, { backgroundColor: 'green' }]}
                  onPress={this.handleConfirmar}
                >
                  <Text style={styles.buttonText}>Confirmar</Text>
                </TouchableOpacity>
              ) : (
                <TouchableOpacity
                  style={[styles.EitButton, { backgroundColor: 'blue' }]}
                  onPress={() => this.setState({ editable: true })}
                >
                  <Text style={styles.buttonText}>Editar</Text>
                </TouchableOpacity>
              )}

             
              {['comanda', 'pedido', 'quantidade', 'extra', 'preco'].map((campo) => (
                <View key={campo} style={{ flexDirection: 'row', alignItems: 'center' }}>
                  <Text>{campo}: </Text>
                  <TextInput
                    style={styles.modalInput}
                    value={String(this.state.pedidoModal[campo] || '')}
                    editable={this.state.editable}
                    onChangeText={(text) => this.alterarPedido(campo, text)}
                    placeholder={`Digite ${campo}`}
                    placeholderTextColor="#999"
                  />
                </View>
              ))}
              <Text>Usuario : {this.state.pedidoModal['username']}</Text>

           
              <TouchableOpacity
                style={styles.closeButton}
                onPress={() => this.setState({ showModal: false, editable: false })}
              >
                <Text style={styles.buttonText}>Fechar</Text>
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
    padding: 10,
  },
  tableRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 10,
  },
  itemContainer: {
    backgroundColor: '#f0f0f0',
    padding: 10,
    borderRadius: 5,
    width: '100%',
  },
  itemText: {
    textAlign: 'center',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalContent: {
    width: '90%',
    backgroundColor: '#fff',
    padding: 20,
    borderRadius: 10,
    alignItems: 'center',
  },
  modalInput: {
    width: '70%',
    fontSize: 16,
    borderWidth: 1,
    borderColor: '#ccc',
    padding: 8,
    marginVertical: 5,
    borderRadius: 5,
  },
  closeButton: {
    backgroundColor: '#FF6347',
    padding: 10,
    borderRadius: 5,
    marginTop: 15,
  },
  EitButton: {
    padding: 10,
    borderRadius: 5,
    marginTop: 15,
  },
  buttonText: {
    color: '#fff',
    fontWeight: 'bold',
  },
});
