// PrinterService.js
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Alert } from 'react-native';

let BLEPrinter, NetPrinter;
async function loadThermal() {
  if (!BLEPrinter || !NetPrinter) {
    const mod = require('react-native-thermal-receipt-printer');
    BLEPrinter = mod.BLEPrinter;
    NetPrinter = mod.NetPrinter;
  }
}

const KEYS = {
  TYPE: 'printer_type',
  MAC: 'printer_mac',
  HOST: 'printer_host',
};

export const PrinterService = {
  async selectBluetoothPrinter() {
    await loadThermal();
    try { await BLEPrinter.init(); } catch (_) {}
    const list = await BLEPrinter.getDeviceList();
    if (!list?.length) {
      Alert.alert('Impressora', 'Nenhum dispositivo pareado encontrado.');
      return;
    }
    const first = list[0];
    const mac = first.inner_mac_address || first.macAddress || first.bdAddress || null;
    if (!mac) {
      Alert.alert('Impressora', 'MAC não encontrado.');
      return;
    }
    await AsyncStorage.setItem(KEYS.MAC, mac);
    await AsyncStorage.setItem(KEYS.TYPE, 'ble');
    const name = first.device_name || first.deviceName || 'Desconhecida';
    Alert.alert('Impressora', `Selecionada: ${name}\nMAC: ${mac}`);
  },

  async printPedido({ mesa, pedido, quant, extra, hora, sendBy }) {
    await loadThermal();
  
    const type = (await AsyncStorage.getItem(KEYS.TYPE)) || 'ble';
  
    // --- Cabeçalho (Mesa) em tamanho grande ---
    const header =
      '\x1B\x61\x01' +   // centralizado
      '\x1B\x21\x30' +   // largura+altura dupla
      `Mesa: ${mesa}\n` +
      '\x1B\x21\x00';    // reset
  
    // --- Detalhes médios ---
    const detalhes =
      '\x1B\x21\x10' +   // altura dupla (um pouco maior)
      `Pedido: ${pedido}\n` +
      `Quant: ${quant}\n` +
      (extra ? `Extra: ${extra}\n` : '') +
      `Hora: ${hora}\n` +
      `SendBy: ${sendBy}\n` +
      '\x1B\x21\x00';    // reset
  
    // feed controlado (2 linhas no fim)
    const feed = '\x1B\x64\x02';
  
    const content = header + detalhes + feed;
  
    if (type === 'net') {
      const host = await AsyncStorage.getItem(KEYS.HOST);
      if (!host) throw new Error('Host da impressora (LAN) não configurado');
      try { await NetPrinter.init(); } catch {}
      await NetPrinter.connectPrinter(host, 9100);
      await NetPrinter.printText(content, {});
      return;
    }
  
    const mac = await AsyncStorage.getItem(KEYS.MAC);
    if (!mac) throw new Error('Impressora Bluetooth não configurada');
    try { await BLEPrinter.init(); } catch {}
    await BLEPrinter.connectPrinter(mac);
    await BLEPrinter.printText(content, {});
  }
  
};
