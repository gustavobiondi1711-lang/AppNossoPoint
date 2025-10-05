import React from "react";
import { KeyboardAvoidingView,View,Text,TextInput,Button,StyleSheet,TouchableOpacity} from "react-native";
import { Picker } from "@react-native-picker/picker"
import { UserContext } from "../UserContext";
import { getSocket } from "../socket";

export default class Cadastro extends React.Component{
  static contextType = UserContext

    constructor(props){
        super(props)
        this.state = {
            username:'',
            senha1:'',
            senha2:'',
            showSenha2:false,
            cargo:'',
        }
      this.socket = null
    }
  

    componentDidMount(){
      this.socket = getSocket();
      
    }

    verificar = () =>{
        const {senha1,senha2,showSenha2,username,cargo} = this.state
        if (username && cargo && senha1){
        if (!showSenha2){
            this.setState({showSenha2:true})
        }
        else if (senha2!==senha1){
            alert('senhas conflitantes')
            this.setState({senha2:''})
          }
        else{
            this.socket.emit('cadastrar',{username,senha:senha1,cargo})

            this.setState({username:'',senha1:'',senha2:'',showSenha2:false,cargo:''})
        } 
      }
      else if (!username){
        alert('É preciso ter um username para cadastrar')
      }
      else if(!cargo){
        alert('É preciso selecionar um cargo para cadastrar')
      }
      else if(!senha1){
        alert('É preciso ter uma senha para cadastrar')
      }
    }

    render() {

      const cargos = ['Colaborador', 'ADM', 'Entregador', 'Cozinha']
      const {cargo} = this.state
        return (
          <View style={styles.container}>
            <Text style={styles.title}>Cadastro</Text>
            <KeyboardAvoidingView  behavior='padding'>
            <TextInput
              style={styles.input}
              placeholder="Usuario"
              placeholderTextColor="#999"
              value={this.state.username}
              onChangeText={(username) => this.setState({ username })}
            />
              <Picker
          selectedValue={cargo}
          onValueChange={value => this.setState({ cargo: value })}
          style={styles.picker}
        >
          {cargos
          .map(item => (
              <Picker.Item key={item} label={item} value={item} />
            ))
          }
        </Picker>
            <TextInput
            style={styles.input}
              secureTextEntry={true}
              placeholder="Senha"
              placeholderTextColor="#999"
              value={this.state.senha1}
              onChangeText={(senha1) => this.setState({ senha1 })}
            />
            {this.state.showSenha2 && (
                <TextInput
                style={styles.input}
                  secureTextEntry={true}
                  placeholder="Confirmar Senha"
                  placeholderTextColor="#999"
                  value={this.state.senha2}
                  onChangeText={(senha2) => this.setState({ senha2 })}
                />
            )}
            <Button
              title="Cadastrar"
              onPress={this.verificar}
            />
            </KeyboardAvoidingView>
          </View>
        );
      }
}

const styles = StyleSheet.create({
    container: {
      flex: 2,
      justifyContent: 'center',
      alignItems: 'center',
    },
    title: {
      fontSize: 24,
      marginBottom: 20,
    },
    input: {
      height: 40,
      borderColor: 'gray',
      borderWidth: 1,
      paddingHorizontal: 50,
      borderRadius: 5,
      marginBottom: 10,
    },
    dropdownOptionSelecionado: {
      backgroundColor: '#2196F3',
      borderRadius: 6,
    },
    dropdownTextoSelecionado: {
      color: 'white',
      fontWeight: 'bold',
    },
    picker: {
      height: 50,            // deixa uma altura visível
      width: 250,            // ou '100%' se quiser ocupar toda a largura do pai
      color: '#000',         // cor do texto
      backgroundColor: '#fff', // fundo branco garante contraste
      borderWidth: 1,
      borderColor: '#ccc',
      marginVertical: 10,
    }
    
  });  