import React, { createContext, useState,useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Create the User Context
export const UserContext = createContext();

// Create a UserProvider component that wraps the app and provides the user state
export const UserProvider = ({ children }) => {
  const [user, setUser] = useState({ username: '', cargo: '', token: '' });
  const [isLoggedIn, setIsLoggedIn] = useState(true);
  const [loading, setLoading] = useState(true);

  return (
    <UserContext.Provider value={{ user, setUser,isLoggedIn,setIsLoggedIn,loading,setLoading}}>
      {children}
    </UserContext.Provider>
  );
};