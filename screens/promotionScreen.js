
import React, { useEffect, useState, useMemo, useRef } from 'react';
import {
  StyleSheet,
  Text,
  View,
  FlatList,
  TouchableOpacity,
  Modal,
  TextInput,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  StatusBar,
} from 'react-native';
import { io, Socket } from 'socket.io-client';
import { API_URL } from './url';
import { getSocket } from '../socket';


// Componente para o Modal de Criação/Edição de Promoção
const PromotionModal = ({ visible, onClose, onSave, promotion, produtosCardapio }) => {
  const isEditing = !!promotion;

  const [name, setName] = useState('');
  const [type, setType] = useState('percentage');
  const [value, setValue] = useState('');
  const [endDate, setEndDate] = useState('');
  const [selectedProducts, setSelectedProducts] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');

  // repopula quando 'promotion' muda
  useEffect(() => {
    if (promotion) {
      setName(promotion.name);
      setType(promotion.type);
      setValue(String(promotion.value));
      setEndDate(promotion.endDate);
      setSelectedProducts(JSON.parse(promotion.products));
      setSearchTerm('');
    } else {
      setName('');
      setType('percentage');
      setValue('');
      setEndDate('');
      setSelectedProducts([]);
      setSearchTerm('');
    }
  }, [promotion]);

  const availableProducts = useMemo(() => {
    if (!searchTerm) return [];
    const selectedIds = new Set(selectedProducts.map(p => p.id));
    return (produtosCardapio || []).filter(
      p =>
        !selectedIds.has(p.id) &&
        (p.item || '').toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [searchTerm, selectedProducts, produtosCardapio]);

  const addProduct = (product) => {
    setSelectedProducts(prev => [...prev, product]);
    setSearchTerm('');
  };

  const removeProduct = (productId) => {
    setSelectedProducts(prev => prev.filter(p => p.id !== productId));
  };

  const handleSave = () => {
    if (!name || !value || !endDate || selectedProducts.length === 0) {
      alert('Por favor, preencha todos os campos.');
      return;
    }
    const promotionData = {
      id: isEditing ? promotion.id : Date.now().toString(),
      name,
      type,
      value: parseFloat(value) || 0,
      endDate,
      status: 'active',
      products: selectedProducts,
    };
    onSave(promotionData);
    onClose();
  };

  return (
    <Modal visible={visible} animationType="slide" transparent={true} onRequestClose={onClose}>
      <KeyboardAvoidingView 
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        style={styles.modalBackdrop}
      >
        <View style={styles.modalContainer}>
          <ScrollView showsVerticalScrollIndicator={false}>
            <Text style={styles.modalTitle}>{isEditing ? 'Editar Promoção' : 'Criar Nova Promoção'}</Text>

            <Text style={styles.label}>Nome da Promoção</Text>
            <TextInput style={styles.input} value={name} onChangeText={setName} placeholder="Ex: Promoção de Verão"  placeholderTextColor="#999"/>

            <Text style={styles.label}>Tipo de Desconto</Text>
            <View style={styles.typeSelectorContainer}>
              <TouchableOpacity
                style={[styles.typeButton, type === 'percentage' && styles.typeButtonActive]}
                onPress={() => setType('percentage')}
              >
                <Text style={[styles.typeButtonText, type === 'percentage' && styles.typeButtonTextActive]}>Porcentagem (%)</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.typeButton, type === 'value' && styles.typeButtonActive]}
                onPress={() => setType('value')}
              >
                <Text style={[styles.typeButtonText, type === 'value' && styles.typeButtonTextActive]}>Valor Fixo (R$)</Text>
              </TouchableOpacity>
            </View>

            <Text style={styles.label}>Valor</Text>
            <TextInput style={styles.input} value={value} onChangeText={setValue} placeholder={type === 'percentage' ? "Ex: 15 (para 15%)" : "Ex: 10 (para R$10)"} keyboardType="numeric" placeholderTextColor="#999"/>

            <Text style={styles.label}>Válida até</Text>
            {/* Em um app real, use um componente de Date Picker */}
            <TextInput style={styles.input} value={endDate} onChangeText={setEndDate} placeholder="AAAA-MM-DD" placeholderTextColor="#999"/>

            <Text style={styles.label}>Produtos na Promoção</Text>
            <TextInput style={styles.input} value={searchTerm} onChangeText={setSearchTerm} placeholder="Pesquisar produto para adicionar..." placeholderTextColor="#999"/>

            {/* Resultados da Pesquisa */}
            {availableProducts.length > 0 && (
              <View style={styles.searchResultsContainer}>
                {availableProducts.map(product => (
                  <TouchableOpacity key={product.id} style={styles.searchResultItem} onPress={() => addProduct(product)}>
                    <Text>{product.item}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            )}

            {/* Produtos Selecionados */}
            <View style={styles.selectedProductsContainer}>
              {selectedProducts.length > 0 ? (
                selectedProducts.map(product => (
                  <View key={product.id} style={styles.selectedProductItem}>
                    <Text style={styles.selectedProductText}>{product.item}</Text>
                    <TouchableOpacity onPress={() => removeProduct(product.id)}>
                      <Text style={styles.removeButtonText}>X</Text>
                    </TouchableOpacity>
                  </View>
                ))
              ) : (
                <Text style={styles.emptyText}>Nenhum produto adicionado.</Text>
              )}
            </View>
          </ScrollView>

          <View style={styles.modalActions}>
            <TouchableOpacity style={[styles.button, styles.buttonClose]} onPress={onClose}>
              <Text style={styles.buttonText}>Cancelar</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.button, styles.buttonSave]} onPress={handleSave}>
              <Text style={styles.buttonText}>Salvar</Text>
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
};


// Componente principal da tela
export default function PricesManagement() {
  const [promotions, setPromotions] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [selectedPromotion, setSelectedPromotion] = useState(null);
  const socketRef = useRef(null); // <<< CORRETO NO JS
  const [produtosCardapio, setProdutosCardapio] = useState([]);
  // mostra só expiradas quando true; padrão: só ativas
const [showExpiredOnly, setShowExpiredOnly] = useState(false);

const filteredPromotions = useMemo(() => {
  return promotions.filter(p =>
    showExpiredOnly ? p.status === 'expired' : p.status === 'active'
  );
}, [promotions, showExpiredOnly]);

  

useEffect(() => {
  // pega a instância global (não cria várias conexões)
  socketRef.current = getSocket();
  const s = socketRef.current;

  // handlers estáveis
  const onPromotionsData = (promotion) => {
    if (promotion) setPromotions(promotion);
    else console.warn('Resposta de promoções inválida:', promotion);
  };

  const onRespostaItensPromotion = (data) => {
    if (data && data.dataCardapio) {
      setProdutosCardapio(data.dataCardapio);
    } else {
      console.warn('Resposta de cardápio inválida:', data);
    }
  };

  // pedir dados
  s.emit('getPromotions', false);
  s.on('promotionsData', onPromotionsData);

  s.emit('getItensPromotion', false);
  s.on('respostaItensPromotion', onRespostaItensPromotion);

  return () => {
    // remova exatamente os listeners adicionados
    s.off('promotionsData', onPromotionsData);
    s.off('respostaItensPromotion', onRespostaItensPromotion);
    // ❌ não desconecte aqui — o socket é global
    // s.disconnect();
    socketRef.current = null;
  };
}, []);

  const handleOpenCreateModal = () => {
    setSelectedPromotion(null);
    setIsModalVisible(true);
  };

  const handleOpenEditModal = (promotion) => {
    setSelectedPromotion(promotion);
    setIsModalVisible(true);
  };

  const handleCloseModal = () => {
    setIsModalVisible(false);
    setSelectedPromotion(null);
  };

  const handleSavePromotion = (promotionData) => {
    const isEditing = promotions.some(p => p.id === promotionData.id);
    let actionType;
    if (isEditing) {
      setPromotions(prev => prev.map(p => (p.id === promotionData.id ? promotionData : p)));
      actionType = 'update';
    } else {
      setPromotions(prev => [promotionData, ...prev]);
      actionType = 'create';
    }
    socketRef.current?.emit('savePromotion', {
      promotionData,
      emitirBroadcast: true,
      type: actionType,
  });
  };

  const renderPromotionItem = ({ item }) => {
    const isExpired = item.status === 'expired';
    return (
      <View style={styles.itemContainer}>
        <TouchableOpacity onPress={() => handleOpenEditModal(item)} style={styles.itemClickableArea}>
          <Text style={styles.itemTitle}>{item.name}</Text>
          <Text style={styles.itemSubtitle}>Válida até: {item.endDate}</Text>
        </TouchableOpacity>
        <View style={[styles.statusBadge, isExpired ? styles.statusBadgeExpired : styles.statusBadgeActive]}>
          <Text style={styles.statusText}>{item.status}</Text>
        </View>
      </View>
    );
  };

  return (
    <KeyboardAvoidingView style={styles.container}>
      <StatusBar barStyle="dark-content" />
      <View style={styles.header}>
      <Text style={styles.title}>Gerenciar Promoções</Text>

      <TouchableOpacity
        onPress={() => setShowExpiredOnly(prev => !prev)}
        style={{ paddingHorizontal: 12, paddingVertical: 8, borderRadius: 12, backgroundColor: '#eee', marginLeft: 12 }}
      >
        <Text style={{ fontWeight: '600' }}>
          {showExpiredOnly ? 'Ver ativas' : 'Ver expiradas'}
        </Text>
      </TouchableOpacity>
    </View>


      <FlatList
        data={filteredPromotions}
        renderItem={renderPromotionItem}
        keyExtractor={(item) => item.id.toString()}
        contentContainerStyle={styles.list}
        ListEmptyComponent={<Text style={styles.emptyText}>Nenhuma promoção criada.</Text>}
      />

      <TouchableOpacity style={styles.fab} onPress={handleOpenCreateModal}>
        <Text style={styles.fabText}>+</Text>
      </TouchableOpacity>

      <PromotionModal
        visible={isModalVisible}
        onClose={handleCloseModal}
        onSave={handleSavePromotion}
        promotion={selectedPromotion}
        produtosCardapio={produtosCardapio}
      />
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    padding: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#ddd',
    backgroundColor: '#fff',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
  },
  list: {
    padding: 20,
  },
  itemContainer: {
    backgroundColor: '#fff',
    padding: 20,
    borderRadius: 12,
    marginBottom: 15,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  itemClickableArea: {
      flex: 1,
  },
  itemTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
  },
  itemSubtitle: {
    fontSize: 14,
    color: '#666',
    marginTop: 4,
  },
  statusBadge: {
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderRadius: 12,
  },
  statusBadgeActive: {
    backgroundColor: '#d4edda',
  },
  statusBadgeExpired: {
    backgroundColor: '#f8d7da',
  },
  statusText: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#333',
  },
  fab: {
    position: 'absolute',
    bottom: 30,
    right: 30,
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: '#007bff',
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 4,
    elevation: 8,
  },
  fabText: {
    color: '#fff',
    fontSize: 30,
    lineHeight: 30,
  },
  emptyText: {
    textAlign: 'center',
    marginTop: 20,
    color: '#666',
  },
  // Estilos do Modal
  modalBackdrop: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: 'rgba(0,0,0,0.5)',
  },
  modalContainer: {
    backgroundColor: 'white',
    height: '90%',
    borderTopRightRadius: 20,
    borderTopLeftRadius: 20,
    padding: 20,
  },
  modalTitle: {
    fontSize: 22,
    fontWeight: 'bold',
    marginBottom: 20,
    textAlign: 'center',
  },
  label: {
    fontSize: 16,
    color: '#333',
    marginBottom: 8,
    marginTop: 10,
    fontWeight: '500',
  },
  input: {
    backgroundColor: '#f0f0f0',
    borderRadius: 8,
    padding: 15,
    fontSize: 16,
    marginBottom: 10,
  },
  typeSelectorContainer: {
    flexDirection: 'row',
    marginBottom: 10,
  },
  typeButton: {
    flex: 1,
    padding: 15,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#ccc',
    alignItems: 'center',
    marginHorizontal: 5,
  },
  typeButtonActive: {
    backgroundColor: '#007bff',
    borderColor: '#007bff',
  },
  typeButtonText: {
    color: '#333',
  },
  typeButtonTextActive: {
    color: '#fff',
    fontWeight: 'bold',
  },
  searchResultsContainer: {
    backgroundColor: '#f9f9f9',
    borderRadius: 8,
    marginTop: 5,
    maxHeight: 150,
  },
  searchResultItem: {
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  selectedProductsContainer: {
      marginTop: 10,
  },
  selectedProductItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#e9ecef',
    padding: 12,
    borderRadius: 8,
    marginBottom: 8,
  },
  selectedProductText: {
    color: '#333',
  },
  removeButtonText: {
    color: 'red',
    fontWeight: 'bold',
    fontSize: 16,
    padding: 5,
  },
  modalActions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 20,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#eee'
  },
  button: {
    flex: 1,
    padding: 15,
    borderRadius: 8,
    alignItems: 'center',
    marginHorizontal: 5,
  },
  buttonSave: {
    backgroundColor: '#28a745',
  },
  buttonClose: {
    backgroundColor: '#6c757d',
  },
  buttonText: {
    color: 'white',
    fontWeight: 'bold',
    fontSize: 16,
  },
});