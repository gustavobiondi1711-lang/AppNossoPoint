import React, { useContext } from 'react';
import { FlatList, View, StyleSheet, Text, RefreshControl, Button,TouchableOpacity ,Modal, Alert} from 'react-native';
import { UserContext } from '../UserContext'; // Import the UserContext
import { API_URL } from "./url";
import { Picker } from "@react-native-picker/picker";
import io from 'socket.io-client';
import { BLEPrinter } from 'react-native-thermal-receipt-printer';
import { askBtPermissions } from '../permissions';
import { PrinterService } from '../PrinterService';
import { getSocket } from '../socket';

export default class ChoseUser extends React.Component {
  static contextType = UserContext;

  constructor(props) {
    super(props);
    this.state = {
      data: [], // Lista de dados de usuários// Define se o usuário tem permissão para ver a lista
      refreshing: false, // Estado para o controle de pull-to-refresh
      showModal:false,
      editCargo:'',
      usuarioSelected:'',
      cargoUsuarioSelected:'',
      senhaUsuarioSelected:'',
      remover:'',
      idUsuarioSelected:'',
      cargos: [ 'Colaborador', 'ADM', 'Entregador', 'Cozinha' ],
    };
    this.socket = null;
  }

  componentDidMount() {
    const { user } = this.context || {};
    this.socket = getSocket();

    // registra o listener UMA vez com referência estável
    this.socket.on("usuarios", this.handleUsuarios);

    // dispara a primeira carga
    this.fetchUsers();
  }

  componentWillUnmount() {
    if (this.socket) {
      this.socket.off("usuarios", this.handleUsuarios);
      // não desconecte o socket global aqui
    }
  }

  // listener estável para conseguir dar off corretamente
  handleUsuarios = (data) => {
    if (data) {
      this.setState({ data: data.users ?? [], refreshing: false });
    } else {
      this.setState({ refreshing: false });
    }
  };

  fetchUsers = () => {
    const { user } = this.context || {};
    this.setState({ refreshing: true }, () => {
      // apenas emite — o listener já está registrado
      this.socket.emit("users", false);
    });
  };


  Liberar = (id, numero) => {
    this.socket.emit('permitir', { id, numero })
  };
  HandleEditCargo(){
    console.log('entrou handle')
    const{cargoUsuarioSelected,usuarioSelected}=this.state
    this.socket.emit("editCargo",{usuario:usuarioSelected,cargo:cargoUsuarioSelected})
    this.setState({editCargo:cargoUsuarioSelected})
    
  };
  Remover(){
    const {idUsuarioSelected} = this.state
    this.socket.emit('Delete_user',{id:idUsuarioSelected})
    this.setState({idUsuarioSelected:'',cargoUsuarioSelected:'',senhaUsuarioSelected:'',showModal:false,usuarioSelected:''})
  }
  render() {
    const { data,refreshing,showModal } = this.state;

    const { cargoUsuarioSelected, cargos,editCargo } = this.state;

    return (
      <View style={styles.container}>
         <Button
        title="Listar dispositivos"
        onPress={async () => {
          try {
            await BLEPrinter.init();
            const list = await BLEPrinter.getDeviceList();
            console.log('BT devices:', list);
          } catch (e) {
            console.log('Erro listar:', e);
          }
        }}
      />
      <Button
  title="Selecionar impressora Bluetooth"
  onPress={async () => {
    try {
      await askBtPermissions();                 // garante permissão Android 12+
      await PrinterService.selectBluetoothPrinter(); // abre lista pareada e salva MAC
    } catch (e) {
      console.log('Erro ao selecionar:', e);
    }
  }}
/>
<Button
  title="Imprimir teste"
  onPress={async () => {
    try {
      await PrinterService.printPedido({
        mesa: 'teste',
        pedido: 'testee pedido',
        quant: '2',
        extra: 'gelo e teste',
        hora: '12:00',
        sendBy: 'testador',
      });
    } catch (e) {
      console.log('Erro ao imprimir:', e);
    }
  }}
/>


      <FlatList
        data={data}
        keyExtractor={(item, index) => index.toString()}
        renderItem={({ item }) => (
          <View style={styles.userCard}>
            <Text style={styles.userInfo}>👤 {item.username}</Text>
            <Text style={styles.userInfo}>🔒 {item.senha}</Text>
            <View style={styles.buttonRow}>
              {item.liberado === '0' ? (
                <TouchableOpacity
                  style={styles.liberar}
                  onPress={() => this.Liberar(item.id, '1')}
                >
                  <Text style={styles.buttonText}>Liberar</Text>
                </TouchableOpacity>
              ) : (
                <TouchableOpacity
                  style={styles.bloquear}
                  onPress={() => this.Liberar(item.id, '0')}
                >
                  <Text style={styles.buttonText}>Bloquear</Text>
                </TouchableOpacity>
              )}
              {!showModal && (
            <TouchableOpacity
                  style={styles.editar}
                  onPress={() => this.setState({showModal:true,usuarioSelected:item.username,cargoUsuarioSelected:item.cargo,editCargo:item.cargo,senhaUsuarioSelected:item.senha,idUsuarioSelected:item.id})}
                >
                  <Text style={styles.buttonText}>Editar</Text>
            </TouchableOpacity>
              )}
            </View> 
          </View>
        )}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={this.fetchUsers}
          />
        }
      />
      <Modal
      animationType='fade'
      trasnparent={true}
      visible={showModal}
      onRequestClose={()=> this.setState({showModal:false})}
      >
        <View style={styles.ModalContainer}>
          <View style={styles.ModalHeader}>
          <TouchableOpacity
              style={styles.setaVoltar}
              onPress={() =>
                  this.setState({
                    showModal:false,
                    })}
            >
              <Text style={styles.setaTexto}>{'\u2190'}</Text>
            </TouchableOpacity>
            <Text style={styles.headerText}>Usuario: 👤 {this.state.usuarioSelected}</Text>
          </View>
          <Picker
          selectedValue={cargoUsuarioSelected}
          onValueChange={value => this.setState({ cargoUsuarioSelected: value })}
          style={styles.picker}
        >
          <Picker.Item
            label={cargoUsuarioSelected || 'Selecionar Cargo'}
            value={cargoUsuarioSelected || ''}
          />
          
          {cargos
            .filter(item => item !== cargoUsuarioSelected)
            .map(item => (
              <Picker.Item key={item} label={item} value={item} />
            ))
          }
        </Picker>
      {cargoUsuarioSelected!==editCargo &&(
        <Button title="Confirma Cargo" onPress={() => this.HandleEditCargo()}/>
      )}
      <Button title='Remover' onPress={()=>{
        Alert.alert(
          "Remover usuario?",
          "Tem certeza que deseja remover este usuario?",
          [
            {text:'Cancelar',style:"cancel"},
            {text:'REMOVER', onPress: ()=> this.Remover()}
          ]
        )
      }}/>
      
          </View>
        </Modal> 
    </View>
    );
  }
}
const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
  },
  userCard: {
    backgroundColor: '#fff',
    padding: 15,
    borderRadius: 10,
    marginBottom: 15,
    elevation: 3, // Android sombra
    shadowColor: '#000', // iOS sombra
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  userInfo: {
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 10,
  },
  buttonRow: {
    flexDirection: 'row',
    justifyContent: 'flex-start',
    gap: 10,
  },
  liberar: {
    backgroundColor: '#4CAF50',
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 6,
  },
  bloquear: {
    backgroundColor: '#f44336',
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 6,
  },
  editar:{
    backgroundColor: 'blue',
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 6,
  },
  buttonText: {
    color: 'white',
    fontWeight: '600',
  },
  ModalContainer:{
    backgroundColor:'white',
    marginVertical:40,
    marginHorizontal:20,
    borderRadius:10,
    borderWidth:2,
    borderColor:'black',
    flex:1,
  },
  headerText:{
    fontSize: 22,
    fontWeight:'bold',
    marginLeft: 16,
  },
  ModalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#ccc',
  },
  setaTexto: {
    fontSize: 30,
    color: '#333',
  },
  setaVoltar:{
    left:10,
    marginRight:20,
  },
  picker: {
    height: 50,
    width: '100%',
  },
});
