import React from 'react';
import { View, FlatList, Text, StyleSheet, Button, RefreshControl, } from 'react-native';
import { UserContext } from '../UserContext';
import { getSocket } from '../socket';

export default class Cozinha extends React.Component {
  static contextType = UserContext;
  constructor(props) {
    super(props);
    this.state = {
      data: [],
      data_filtrado: [],
      showFiltrado: false,
      refreshing: false, // Estado para gerenciar o "pull-to-refresh"
    };
    this.refreshData = this.refreshData.bind(this);
    this.socket = null;
  }

  componentDidMount() {
    this.socket = getSocket();

    // registra o listener UMA vez, com referência estável
    this.socket.on("respostaPedidos", this.handleRespostaPedidos);

    // primeira carga
    this.refreshData();
  }

  componentWillUnmount() {
    if (this.socket) {
      this.socket.off("respostaPedidos", this.handleRespostaPedidos);
      // não desconecte o socket global aqui
    }
    if (this.refreshTimeout) clearTimeout(this.refreshTimeout);
  }

  // --------- handlers ----------
  handleRespostaPedidos = (dados) => {
    if (!dados?.dataPedidos) {
      this.setState({ refreshing: false });
      return;
    }

    const data_temp = dados.dataPedidos.filter((item) => item.categoria === "3");
    const data_temp_filtrado = data_temp.filter((item) => item.estado !== "Pronto");

    this.setState({
      data: data_temp,
      data_filtrado: data_temp_filtrado,
      refreshing: false,
    });
  };

  // --------- refresh ----------
  refreshData = () => {
    this.setState({ refreshing: true }, () => {
      this.socket.emit("getPedidos", false);

      // Fallback para não ficar travado caso o backend não responda
      if (this.refreshTimeout) clearTimeout(this.refreshTimeout);
      this.refreshTimeout = setTimeout(() => {
        this.setState({ refreshing: false });
      }, 5000); // 5s
    });
  };


  alterar_estado(id, estado) {
    this.socket.emit('inserir_preparo', { id, estado });
  }

  filtrar = () => {
    this.setState(prevState => ({
      showFiltrado: !prevState.showFiltrado,
    }));
  };

  render() {
    const dataToShow = this.state.showFiltrado
      ? this.state.data
      : this.state.data_filtrado;

    return (
      <View style={styles.container}>
        <View style={styles.tableHeader}>
          <Text style={styles.headerText}>Comanda</Text>
          <Text style={styles.headerText}>Pedido</Text>
         
          {this.state.showFiltrado ? (
            <Button title="Filtrar" onPress={this.filtrar} />
          ) : (
            <Button title="Todos" onPress={this.filtrar} />
          )}
        </View>
        <FlatList
          data={dataToShow}
          renderItem={({ item }) => (
            <View style={styles.tableRow}>
             {item?.comanda ? <Text style={styles.itemText}>{item.comanda}</Text> : null}
              <Text style={styles.itemText}>{item.pedido} {item.extra}</Text>
            
              {item.estado === "Em Preparo" ? (
                <View>
                <Button color='orange' title="Pronto" onPress={() => this.alterar_estado(item.id, 'Pronto')} />
                  </View>
              ) : item.estado === "A Fazer" ? (
                <Button color='blue'title="Começar" onPress={() => this.alterar_estado(item.id, 'Em Preparo')} />
              ) : (
                <Button color='green'title="Desfazer" onPress={() => this.alterar_estado(item.id, 'A Fazer')} />
              )}
            </View>
          )}
          keyExtractor={(item, index) => index.toString()}
          refreshControl={
            <RefreshControl
              refreshing={this.state.refreshing}
              onRefresh={this.refreshData} // Chama o método de atualização ao puxar para baixo
            />
          }
        />
      </View>
    );
  }
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 10,
  },
  tableHeader: {
    flexDirection: 'row',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#ddd',
  },
  headerText: {
    flex: 1,
    fontSize: 18,
    fontWeight: 'bold',
  },
  tableRow: {
    flexDirection: 'row',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#ddd',
  },
  itemText: {
    flex: 1,
    fontSize: 16,
  },
});