import React, { useState, useEffect, useContext } from 'react';
import { View, Text, TextInput, Button, StyleSheet, KeyboardAvoidingView, Alert,ActivityIndicator } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { UserContext } from '../UserContext';
import { useToken } from '../TokenContext';
import { API_URL } from './url';

export default function Login({ navigation }) {
  const { setUser } = useContext(UserContext);
  const { expoPushToken } = useToken();
  const [username, setUsername] = useState('');
  const [senha, setSenha] = useState('');
  const {isLoggedIn, setIsLoggedIn} = useContext(UserContext);
  const {loading,setLoading}=useContext(UserContext)

  useEffect(() => {
    async function checkLogin() { 
      setLoading(true)
      const savedUsername = await AsyncStorage.getItem('username');
      const savedToken = await AsyncStorage.getItem('userToken');
      const savedSenha = await AsyncStorage.getItem('usersenha');
      const senhaExpiration = await AsyncStorage.getItem('senhaExpiration');

      if (savedToken && savedUsername && savedSenha && senhaExpiration) {
        const currentTime = Date.now();
        if (currentTime < parseInt(senhaExpiration)) {
          setUsername(savedUsername);
          setSenha(savedSenha);
          setIsLoggedIn(true);
          mandarValores(savedUsername, savedSenha);
        } else {
          await AsyncStorage.removeItem('usersenha');
          await AsyncStorage.removeItem('senhaExpiration');
          setIsLoggedIn(false);
        }
      } else {
        setIsLoggedIn(false);
      }
      setLoading(false)
    }
    checkLogin();
  }, []);

  const generateToken = () => {
    return Math.random().toString(36).substring(2, 7).toUpperCase();
  };

  const login = async (cargo) => {
    const expirationTime = Date.now() + 14 * 60 * 60 * 1000;
    const guardar_token = generateToken();

    await AsyncStorage.setItem('userToken', guardar_token);
    await AsyncStorage.setItem('username', username);
    await AsyncStorage.setItem('usersenha', senha);
    await AsyncStorage.setItem('senhaExpiration', expirationTime.toString());
    setLoading(false)
    // 🔥 Aqui você usa o expoPushToken real
    await fetch(`${API_URL}/salvarTokenCargo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username,
        cargo,
        token: expoPushToken || 'semtoken'
      }),
    });
    setIsLoggedIn(true);
  };

  const mandarValores = async (username, senha) => {
    try {
      const res = await fetch(`${API_URL}/verificar_username`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, senha }),
      });
  
      const data = await res.json();
      if (data.data) {
        setUser({ username, cargo: data.cargo,token: expoPushToken });
        if (!isLoggedIn) login(data.cargo);
      } else {
        Alert.alert('Erro', 'Usuário ou senha inválidos');
      }
    } catch (error) {
      console.error('Erro:', error);
      Alert.alert('Erro', 'Erro de conexão com o servidor');
    }
  };
  
if(loading){
  return  (<View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
  <ActivityIndicator size="large" color="#0000ff" />
  <Text>Carregando...</Text>
</View>)
}
   if (!isLoggedIn) {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Login</Text>
      <KeyboardAvoidingView behavior="padding">
        <TextInput
          style={styles.input}
          placeholder="Usuário"
          placeholderTextColor="#999"
          value={username}
          onChangeText={setUsername}
        />
        <TextInput
          style={styles.input}
          placeholder="Senha"
          placeholderTextColor="#999"
          value={senha}
          onChangeText={setSenha}
        />
        <Button title="Entrar" onPress={() => mandarValores(username, senha)} />
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
});
