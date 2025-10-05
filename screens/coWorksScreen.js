import React from "react";
import { Text,View,ScrollView,StyleSheet,Button,TouchableOpacity} from "react-native";
import { io } from "socket.io-client";
import Icon from 'react-native-vector-icons/FontAwesome';
import { API_URL } from "./url";
import { UserContext } from "../UserContext";
import { getSocket } from "../socket";

export default class CoWorksScreen extends React.Component{
    static contextType = UserContext
constructor(props){
    super(props)
    this.state={
    dataAlteracoes:[],
    dia:'',
    change:0,
    }
    this.socket=null
}

componentDidMount() {
    this.socket = getSocket();

    // listener com referência estável
    this.socket.on("respostaAlteracoes", this.handleRespostaAlteracoes);

    // primeira carga
    this.emitGetAlteracoes();
  }

  componentWillUnmount() {
    if (this.socket) {
      this.socket.off("respostaAlteracoes", this.handleRespostaAlteracoes);
      // não desconectar o socket global aqui
    }
  }

  emitGetAlteracoes = () => {
    this.socket.emit("getAlteracoes", false);
  };

  handleRespostaAlteracoes = (dados) => {
    if (!dados) return;
    const lista = Array.isArray(dados.alteracoes) ? [...dados.alteracoes].reverse() : [];
    this.setState({
      dataAlteracoes: lista,
      dia: dados.hoje ?? null,
    });
  };

mudarDia = (change) =>{
    if (change<=0){
    this.socket.emit("getAlteracoes",{emitir:false,change:change})
    this.setState({change:change})
    }   
}

render(){
    const {change} = this.state
    return(
    <ScrollView>
        <View style={styles.data}>
            <TouchableOpacity onPress={this.abrirCalendario}>
                <Icon name="calendar" size={18} color="#333" style={styles.dateIcon}/>
            </TouchableOpacity>
            <Button title='<' onPress={()=>this.mudarDia(change-1)}/>
            <Text style={styles.dateText}>Dia {this.state.dia}</Text>
            {change!==0 && (
            <Button title='>' onPress={()=>this.mudarDia(change+1)}/>)}
        </View>
        {!!this.state.dataAlteracoes && this.state.dataAlteracoes.map((item , i)=> (
            <View key={i} style={styles.userCard}>
                <Text style={styles.userInfo}>{item.tabela} as {item.horario}</Text>
                <Text>Na {item.tela}, {item.usuario} {item.tipo} {item.alteracao}</Text>
            </View>
        ))}
    </ScrollView>
    )
}
}
const styles =StyleSheet.create({
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
      dateIcon: {
        fontSize: 18,
        marginRight: 8,
      },
      dateText: {
        fontSize: 16,
        fontWeight: 'bold',
        color: '#333',
        padding:5,
      },
      data:{
        flexDirection:"row",
        padding:10,
        alignItems: 'center',
        margin: 8,
      },
      userInfo: {
        fontSize: 16,
        fontWeight: 'bold',
        marginBottom: 10,
      },
})