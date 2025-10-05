import { Audio } from 'expo-av';
import React, { useEffect, useRef, useState } from 'react';
import { Alert, Animated, Easing, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import Svg, { Defs, Ellipse, Filter, FeBlend, FeColorMatrix, FeComposite, FeFlood, FeGaussianBlur, FeMorphology, FeOffset, G, Path } from 'react-native-svg';

const AnimatedG = Animated.createAnimatedComponent(G);


export default function HomeScreen() {
  const [isActive, setIsActive] = useState(false);
  const [hasPermission, setHasPermission] = useState(false);
  const [currentScale, setCurrentScale] = useState(1);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('Disconnected');
  const [animationTime, setAnimationTime] = useState(0);
  const rotateValue = new Animated.Value(0);
  const recordingRef = useRef<Audio.Recording | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const animationIntervalRef = useRef<number | null>(null);
  
  // Animation values for each rotating group
  const rotateA = useRef(new Animated.Value(0)).current;
  const rotateB = useRef(new Animated.Value(0)).current;
  const rotateC = useRef(new Animated.Value(0)).current;
  const rotateD = useRef(new Animated.Value(0)).current;
  const rotateE = useRef(new Animated.Value(0)).current;
  const rotateF = useRef(new Animated.Value(0)).current;

  // Request audio permissions on component mount
  useEffect(() => {
    requestAudioPermission();
    initializeWebSocket();
    
    // Start animation loop
    animationIntervalRef.current = setInterval(() => {
      setAnimationTime(Date.now());
    }, 50); // Update every 50ms for smooth animation
    
    return () => {
      stopAudioRecording();
      disconnectWebSocket();
      if (animationIntervalRef.current) {
        clearInterval(animationIntervalRef.current);
      }
    };
  }, []);

  const initializeWebSocket = () => {
    const webSocketURL = 'ws://10.253.143.247:3001';
    try {
      // Create a new WebSocket instance
      const socket = new WebSocket(webSocketURL);
      socketRef.current = socket;

      // Event handler for when the WebSocket connection is established
      socket.onopen = () => {
        console.log('WebSocket connected.');
        setIsConnected(true);
        setConnectionStatus('connected');
        
        // Send client registration message
        const registerMessage = {
          type: 'register_client',
          client_type: 'phone',
          timestamp: Date.now(),
          capabilities: {
            audio_streaming: true,
            sample_rate: 16000,
            channels: 1,
            format: 'raw'
          }
        };
        
        socket.send(JSON.stringify(registerMessage));
        console.log('Sent client registration:', registerMessage);
      };

      // Event handler for when the WebSocket receives a message
      socket.onmessage = (event) => {
        try {
          // Parse the received message
          const data = JSON.parse(event.data);
          console.log('WebSocket message received:', data);
        } catch (error) {
          console.log('WebSocket message received (raw):', event.data);
        }
      };

      // Event handler for WebSocket errors
      socket.onerror = (error) => {
        console.error('WebSocket error:', error);
        setConnectionStatus('Connection Error');
      };

      // Event handler for when the WebSocket connection is closed
      socket.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        setIsConnected(false);
        setIsActive(false);
        setConnectionStatus('Disconnected');
        socketRef.current = null;
      };

    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      setConnectionStatus('Connection Failed');
    }
  };


  const disconnectWebSocket = () => {
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
      setIsConnected(false);
      setIsActive(false);
      setConnectionStatus('Disconnected');
    }
  };

  const requestAudioPermission = async () => {
    try {
      const { status } = await Audio.requestPermissionsAsync();
      if (status === 'granted') {
        setHasPermission(true);
        await Audio.setAudioModeAsync({
          allowsRecordingIOS: true,
          playsInSilentModeIOS: true,
        });
      } else {
        Alert.alert('Permission Required', 'Microphone permission is required for audio visualization');
      }
    } catch (error) {
      console.error('Error requesting audio permission:', error);
    }
  };

  const startAudioRecording = async () => {
    if (!hasPermission) return;

    try {
      // Create audio recording for streaming
      const audioRecording = new Audio.Recording();
      await audioRecording.prepareToRecordAsync({
        android: {
          extension: '.raw',
          outputFormat: Audio.AndroidOutputFormat.DEFAULT,
          audioEncoder: Audio.AndroidAudioEncoder.DEFAULT,
          sampleRate: 16000,
          numberOfChannels: 1,
          bitRate: 256000,
        },
        ios: {
          extension: '.raw',
          audioQuality: Audio.IOSAudioQuality.HIGH,
          outputFormat: Audio.IOSOutputFormat.LINEARPCM,
          sampleRate: 16000,
          numberOfChannels: 1,
          bitRate: 256000,
          linearPCMBitDepth: 16,
          linearPCMIsBigEndian: false,
          linearPCMIsFloat: false,
          
        },
        web: {
          mimeType: 'audio/wav',
          bitsPerSecond: 256000,
        },
        isMeteringEnabled: true,
      });
      await audioRecording.startAsync();
      recordingRef.current = audioRecording;

      // Start audio streaming interval
      const audioStreamInterval = setInterval(async () => {
        if (recordingRef.current && isConnected && socketRef.current) {
          try {
            // Stop current recording to get the file
            const status = await recordingRef.current.getStatusAsync();
            await recordingRef.current.stopAndUnloadAsync();


            // Get the URI of the recorded audio file
            const uri = recordingRef.current.getURI();


            const volume = (status.metering! + 160) / 160;

            console.log('Volume:', volume);
            
            if (uri && volume > 0.86) {
              console.log('Volume is greater than 0.87, sending audio chunk');
              // Read the actual audio file
              const response = await fetch(uri);
              const audioBlob = await response.blob();
              console.log('Audio blob:', audioBlob);
              
              // Convert blob to array buffer (React Native compatible)
              let audioArrayBuffer;
              if (audioBlob.arrayBuffer) {
                audioArrayBuffer = await audioBlob.arrayBuffer();
              } else {
                // Fallback for React Native
                const reader = new FileReader();
                audioArrayBuffer = await new Promise((resolve, reject) => {
                  reader.onload = () => resolve(reader.result);
                  reader.onerror = reject;
                  reader.readAsArrayBuffer(audioBlob);
                });
              }
              
              // Convert to base64 for transmission
              const base64Audio = btoa(String.fromCharCode(...new Uint8Array(audioArrayBuffer as ArrayBuffer)));
              
              // Send real audio data
              const message = {
                type: 'audio_chunk',
                data: base64Audio,
                timestamp: Date.now(),
                sampleRate: 16000,
                channels: 1,
                size: (audioArrayBuffer as ArrayBuffer).byteLength,
                client_type: 'phone'
              };
              
              socketRef.current.send(JSON.stringify(message));
              console.log(`Sent real audio chunk: ${(audioArrayBuffer as ArrayBuffer).byteLength} bytes`);
            }


            
            // Start recording again for the next chunk
            const newRecording = new Audio.Recording();
            await newRecording.prepareToRecordAsync({
              android: {
                extension: '.raw',
                outputFormat: Audio.AndroidOutputFormat.DEFAULT,
                audioEncoder: Audio.AndroidAudioEncoder.DEFAULT,
                sampleRate: 16000,
                numberOfChannels: 1,
                bitRate: 256000,
              },
              ios: {
                extension: '.raw',
                audioQuality: Audio.IOSAudioQuality.HIGH,
                outputFormat: Audio.IOSOutputFormat.LINEARPCM,
                sampleRate: 16000,
                numberOfChannels: 1,
                bitRate: 256000,
                linearPCMBitDepth: 16,
                linearPCMIsBigEndian: false,
                linearPCMIsFloat: false,
              },
              web: {
                mimeType: 'audio/wav',
                bitsPerSecond: 256000,
              },
              isMeteringEnabled: true,
            });
            await newRecording.startAsync();
            recordingRef.current = newRecording;
            
          } catch (streamError) {
            console.error('Error sending audio chunk:', streamError);
          }
        }
      }, 2000); // Stream audio every 2 seconds

      // Store the audio stream interval so we can clear it later
      (recordingRef.current as any).audioStreamInterval = audioStreamInterval;

    } catch (error) {
      console.error('Error starting audio recording:', error);
    }
  };

  const stopAudioRecording = async () => {
    // Stop audio streaming recording
    if (recordingRef.current) {
      try {
        // Clear the audio stream interval
        const audioStreamInterval = (recordingRef.current as any).audioStreamInterval;
        if (audioStreamInterval) {
          clearInterval(audioStreamInterval);
        }
        
        await recordingRef.current.stopAndUnloadAsync();
        recordingRef.current = null;
        console.log('Audio recording stopped');
      } catch (error) {
        console.error('Error stopping audio recording:', error);
      }
    }
    
    // Reset to base scale when stopping
    setCurrentScale(1.0);
  };

  React.useEffect(() => {
    // Start all rotation animations
    const animations = [
      Animated.loop(Animated.timing(rotateA, { toValue: 1, duration: 8000, easing: Easing.linear, useNativeDriver: true })),
      Animated.loop(Animated.timing(rotateB, { toValue: 1, duration: 10000, easing: Easing.linear, useNativeDriver: true })),
      Animated.loop(Animated.timing(rotateC, { toValue: 1, duration: 9000, easing: Easing.linear, useNativeDriver: true })),
      Animated.loop(Animated.timing(rotateD, { toValue: 1, duration: 12000, easing: Easing.linear, useNativeDriver: true })),
      Animated.loop(Animated.timing(rotateE, { toValue: 1, duration: 11000, easing: Easing.linear, useNativeDriver: true })),
      Animated.loop(Animated.timing(rotateF, { toValue: 1, duration: 9000, easing: Easing.linear, useNativeDriver: true })),
    ];

    animations.forEach(animation => animation.start());

    return () => {
      animations.forEach(animation => animation.stop());
    };
  }, []);

  // Pulsing animation is now handled in the volume monitoring loop

  // Rotation interpolations for each group
  const rotationA = rotateA.interpolate({
    inputRange: [0, 1],
    outputRange: [0, 360],
  });
  
  const rotationB = rotateB.interpolate({
    inputRange: [0, 1],
    outputRange: [0, 360],
  });
  
  const rotationC = rotateC.interpolate({
    inputRange: [0, 1],
    outputRange: [0, -360], // Counter-clockwise
  });
  
  const rotationD = rotateD.interpolate({
    inputRange: [0, 1],
    outputRange: [0, 360],
  });
  
  const rotationE = rotateE.interpolate({
    inputRange: [0, 1],
    outputRange: [0, -360], // Counter-clockwise
  });
  
  const rotationF = rotateF.interpolate({
    inputRange: [0, 1],
    outputRange: [0, 360],
  });

  const toggleActive = async () => {
    console.log('Toggling active state from', isActive, 'to', !isActive);
    const newActiveState = !isActive;
    setIsActive(newActiveState);
    
    if (newActiveState) {
      await startAudioRecording();
    } else {
      await stopAudioRecording();
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.centerContainer}>

        <Text style={styles.text}>echopilot</Text>

        <TouchableOpacity activeOpacity={0.2} onPress={toggleActive} style={styles.svgContainer}>
          


            <Svg width="391" height="391" viewBox="0 0 391 391" fill="none">
      <G id="ai">
        <G id="main" filter="url(#filter0_i)">
          <Ellipse cx="195" cy="195.878" rx="137" ry="130" fill="black" />
        </G>
        <G id="g" filter="url(#filter1_i)">
          <Path
            d="M258.925 321.952C217.208 345.095 172.592 342.312 125.078 313.602C77.5637 284.893 55.7755 241.764 59.7134 184.217C63.6513 126.669 92.3392 89.9343 145.777 74.0127C199.215 58.0912 240.138 64.8972 288.549 94.4308C336.959 123.964 352.887 163.482 336.333 212.984C319.778 262.486 300.643 298.809 258.925 321.952Z"
            fill="none" stroke={isActive ? "#892CDC" : "#111011"} strokeWidth="2" strokeOpacity="0.8" />
        </G>
        <AnimatedG id="f" transform={`translate(195.5, 195.5)  translate(-195.5, -195.5)`}>
          <Path
            d="M326.448 156.236C346.632 212.15 332.809 259.232 284.98 291.481C237.151 323.731 192.504 332.917 149.039 323.041C105.574 313.164 89.3852 282.81 62.4734 237.98C35.5616 193.149 44.0955 149.683 88.0752 113.583C132.055 77.4825 162.066 60.7542 216.109 63.398C270.151 66.0419 306.264 100.321 326.448 156.236Z"
            fill="none" stroke={isActive ? "#892CDC" : "#111011"} strokeWidth="2" strokeOpacity="0.8" />
        </AnimatedG>
        <AnimatedG id="e" transform={`translate(195.5, 195.5) translate(-195.5, -195.5)`}>
          <Path
            d="M308.736 272.285C277.494 310.837 241.385 331.695 202.457 330.853C163.529 330.012 131.724 311.363 90.3165 273.652C48.909 235.941 42.6591 180.041 78.2399 130.975C113.821 81.9087 148.433 66.384 203.478 59.8779C267.756 59.878 301.626 79.7019 321.834 139.983C342.042 200.265 339.977 233.733 308.736 272.285Z"
            fill="none" stroke={isActive ? "#892CDC" : "#111011"} strokeWidth="2" strokeOpacity="0.8" />
        </AnimatedG>
        <AnimatedG id="d" transform={`translate(195.5, 195.5) translate(-195.5, -195.5)`}>
          <Path
            d="M310.393 271.778C277.096 320.326 237.637 341.218 192.017 334.454C146.397 327.691 108.445 303.417 78.163 261.632C47.8806 219.848 47.2907 176.786 76.3933 132.447C105.496 88.1073 144.037 62.6309 192.017 56.0176C239.997 49.4042 280.045 71.5739 312.163 122.527C344.281 173.48 343.691 223.23 310.393 271.778Z"
            fill="none" stroke={isActive ? "#892CDC" : "#111011"} strokeWidth="2" strokeOpacity="0.8" />
        </AnimatedG>
        <AnimatedG id="c" transform={`translate(195.5, 195.5) translate(-195.5, -195.5)`}>
          <Path
            d="M307.832 268.624C269.508 314.707 224.746 336.931 177.547 333.296C130.347 329.662 95.4519 306.621 72.8607 264.173C50.2695 221.725 51.3869 179.861 70.2129 130.581C89.0389 81.3006 124.741 56.7332 177.319 56.8786C229.898 57.0239 268.542 71.6641 305.253 120.799C341.964 169.934 346.157 222.542 307.832 268.624Z"
            fill="none" stroke={isActive ? "#892CDC" : "#111011"} strokeWidth="2" strokeOpacity="0.8" />
        </AnimatedG>
        <AnimatedG id="b" transform={`translate(195.5, 195.5) translate(-195.5, -195.5)`}>
          <Path
            d="M331.624 168.687C347.668 221.613 330.95 272.44 279.471 301.168C227.991 329.896 187.577 329.032 145.905 318.035C105.707 305.685 76.9748 280.125 58.6244 235.997C45.9255 192.116 49.6617 164.211 87.3237 111.256C124.986 58.3013 191.752 38.1339 243.897 64.3134C296.041 90.4928 315.581 115.761 331.624 168.687Z"
            fill="none" stroke={isActive ? "#892CDC" : "#111011"} strokeWidth="2" strokeOpacity="0.8" />
        </AnimatedG>
        <AnimatedG id="a" transform={`translate(195.5, 195.5) translate(-195.5, -195.5)`}>
          <Path   
            d="M326.506 247.112C315.692 300.334 286.086 320.463 219.776 328.226C162.35 330.151 125.891 317.84 89.3915 279.281C52.8915 240.723 45.0065 196.243 65.7364 145.84C86.4663 95.437 130.158 67.4141 184.915 60.2048C239.672 52.9955 281.677 69.9023 310.931 110.925C340.185 151.948 337.32 193.89 326.506 247.112Z"
              fill="none" stroke={isActive ? "#892CDC" : "#111011"} strokeWidth="2" strokeOpacity="0.8" />
        </AnimatedG>
      </G>
      <Defs>
        <Filter id="filter0_i" x="58" y="65.8779" width="274" height="260" filterUnits="userSpaceOnUse"
          colorInterpolationFilters="sRGB">
          <FeFlood floodOpacity="0" result="BackgroundImageFix" />
          <FeBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape" />
          <FeColorMatrix in="SourceAlpha" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0"
            result="hardAlpha" />
          <FeMorphology radius="21" operator="erode" in="SourceAlpha" result="effect1_innerShadow" />
          <FeOffset />
          <FeGaussianBlur stdDeviation="11" />
          <FeComposite in2="hardAlpha" operator="arithmetic" k2="-1" k3="1" />
          <FeColorMatrix type="matrix" values="0 0 0 0 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0.06 0" />
          <FeBlend mode="normal" in2="shape" result="effect1_innerShadow" />
        </Filter>
        <Filter id="filter1_i" x="2.5" y="2.87793" width="386.053" height="385.637" filterUnits="userSpaceOnUse"
          colorInterpolationFilters="sRGB">
          <FeFlood floodOpacity="0" result="BackgroundImageFix" />
          <FeBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape" />
          <FeColorMatrix in="SourceAlpha" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0"
            result="hardAlpha" />
          <FeOffset />
          <FeGaussianBlur stdDeviation="10" />
          <FeComposite in2="hardAlpha" operator="arithmetic" k2="-1" k3="1" />
          <FeColorMatrix type="matrix" values="0 0 0 0 0.418229 0 0 0 0 0.448185 0 0 0 0 0.9125 0 0 0 0.77 0" />
          <FeBlend mode="normal" in2="shape" result="effect1_innerShadow" />
        </Filter>
        <Filter id="filter2_i" x="2" y="1.93799" width="385.898" height="386.199" filterUnits="userSpaceOnUse"
          colorInterpolationFilters="sRGB">
          <FeFlood floodOpacity="0" result="BackgroundImageFix" />
          <FeBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape" />
          <FeColorMatrix in="SourceAlpha" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0"
            result="hardAlpha" />
          <FeOffset />
          <FeGaussianBlur stdDeviation="10" />
          <FeComposite in2="hardAlpha" operator="arithmetic" k2="-1" k3="1" />
          <FeColorMatrix type="matrix" values="0 0 0 0 0.418229 0 0 0 0 0.448185 0 0 0 0 0.9125 0 0 0 0.77 0" />
          <FeBlend mode="normal" in2="shape" result="effect1_innerShadow" />
        </Filter>
        <Filter id="filter3_i" x="55" y="59.8779" width="280" height="271" filterUnits="userSpaceOnUse"
          colorInterpolationFilters="sRGB">
          <FeFlood floodOpacity="0" result="BackgroundImageFix" />
          <FeBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape" />
          <FeColorMatrix in="SourceAlpha" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0"
            result="hardAlpha" />
          <FeOffset />
          <FeGaussianBlur stdDeviation="10" />
          <FeComposite in2="hardAlpha" operator="arithmetic" k2="-1" k3="1" />
          <FeColorMatrix type="matrix" values="0 0 0 0 0.418229 0 0 0 0 0.448185 0 0 0 0 0.9125 0 0 0 0.77 0" />
          <FeBlend mode="normal" in2="shape" result="effect1_innerShadow" />
        </Filter>
        <Filter id="filter4_i" x="55" y="54.8779" width="280.817" height="280.817" filterUnits="userSpaceOnUse"
          colorInterpolationFilters="sRGB">
            <FeFlood floodOpacity="0" result="BackgroundImageFix" />
            <FeBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape" />
          <FeColorMatrix in="SourceAlpha" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0"
            result="hardAlpha" />
          <FeOffset />
          <FeGaussianBlur stdDeviation="10" />
          <FeComposite in2="hardAlpha" operator="arithmetic" k2="-1" k3="1" />
          <FeColorMatrix type="matrix" values="0 0 0 0 0.418229 0 0 0 0 0.448185 0 0 0 0 0.9125 0 0 0 0.77 0" />
          <FeBlend mode="normal" in2="shape" result="effect1_innerShadow" />
        </Filter>
        <Filter id="filter5_i" x="56" y="56.8779" width="278.738" height="276.802" filterUnits="userSpaceOnUse"
          colorInterpolationFilters="sRGB">
            <FeFlood floodOpacity="0" result="BackgroundImageFix" />
          <FeBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape" />
          <FeColorMatrix in="SourceAlpha" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0"
            result="hardAlpha" />
          <FeOffset />
          <FeGaussianBlur stdDeviation="10" />
          <FeComposite in2="hardAlpha" operator="arithmetic" k2="-1" k3="1" />
          <FeColorMatrix type="matrix" values="0 0 0 0 0.418229 0 0 0 0 0.448185 0 0 0 0 0.9125 0 0 0 0.77 0" />
          <FeBlend mode="normal" in2="shape" result="effect1_innerShadow" />
        </Filter>
        <Filter id="filter6_i" x="0" y="0" width="390.838" height="390.84" filterUnits="userSpaceOnUse"
          colorInterpolationFilters="sRGB">
          <FeFlood floodOpacity="0" result="BackgroundImageFix" />
          <FeBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape" />
          <FeColorMatrix in="SourceAlpha" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0"
            result="hardAlpha" />
          <FeOffset />
          <FeGaussianBlur stdDeviation="10" />
          <FeComposite in2="hardAlpha" operator="arithmetic" k2="-1" k3="1" />
          <FeColorMatrix type="matrix" values="0 0 0 0 0.418229 0 0 0 0 0.448185 0 0 0 0 0.9125 0 0 0 0.77 0" />
          <FeBlend mode="normal" in2="shape" result="effect1_innerShadow" />
        </Filter>
        <Filter id="filter7_i" x="35" y="39.8555" width="320.27" height="311.235" filterUnits="userSpaceOnUse"
          colorInterpolationFilters="sRGB">
            <FeFlood floodOpacity="0" result="BackgroundImageFix" />
          <FeBlend mode="normal" in="SourceGraphic" in2="BackgroundImageFix" result="shape" />
          <FeColorMatrix in="SourceAlpha" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 127 0"
            result="hardAlpha" />
          <FeOffset />
          <FeGaussianBlur stdDeviation="10" />
          <FeComposite in2="hardAlpha" operator="arithmetic" k2="-1" k3="1" />
          <FeColorMatrix type="matrix" values="0 0 0 0 0.418229 0 0 0 0 0.448185 0 0 0 0 0.9125 0 0 0 0.77 0" />
          <FeBlend mode="normal" in2="shape" result="effect1_innerShadow" />
          </Filter>
      </Defs>
    </Svg>

        </TouchableOpacity>
       
        <Text style={styles.tapText}>
          {isActive ? 'tap to stop streaming' : 'tap to stream audio'}
        </Text>
        <View style={styles.statusContainer}>
          <Text style={[styles.statusText, { color: isConnected ? '#BC6FF1' : '#fa1f0f' }]}>
            {connectionStatus}
          </Text>
          {!isConnected && (
            <TouchableOpacity 
              style={styles.reconnectButton} 
              onPress={() => {
                disconnectWebSocket();
                console.log('Reconnecting...');
                initializeWebSocket();
              }}
            >
              <Text style={styles.reconnectText}>Reconnect</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  text: {
    fontFamily: "ui-sans-serif, -apple-system, system-ui, sans-serif",
    fontSize: 36,
    color: '#ffffff',
    fontWeight: 'bold',
    
    marginBottom: 60,
  },
  container: {
    flex: 1,
    backgroundColor: '#000000',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  tapText: {
    color: '#888888',
    fontSize: 22,
    fontWeight: '300',
    marginTop: 45,
    letterSpacing: 1,
  },
  glowObject: {
    width: 200,
    height: 200,
    borderRadius: 100,
    position: 'relative',
    justifyContent: 'center',
    alignItems: 'center',
  },
  touchableCenter: {
    position: 'absolute',
    justifyContent: 'center',
    alignItems: 'center',
  },
  touchableCenterInner: {
    width: '100%',
    height: '100%',
    justifyContent: 'center',
    alignItems: 'center',
  },
  orbContainer: {
    width: 200,
    height: 200,
    justifyContent: 'center',
    alignItems: 'center',
    position: 'relative',
  },
  orb: {
    width: 80,
    height: 80,
    borderRadius: 40,
    position: 'absolute',
    shadowOffset: {
      width: 0,
      height: 0,
    },
    shadowOpacity: 0.8,
    shadowRadius: 20,
    elevation: 20,
  },
  orbRing: {
    width: 100,
    height: 100,
    borderRadius: 50,
    borderWidth: 2,
    position: 'absolute',
    shadowOffset: {
      width: 0,
      height: 0,
    },
    shadowOpacity: 0.6,
    shadowRadius: 15,
    elevation: 15,
  },
  particle: {
    width: 8,
    height: 8,
    borderRadius: 4,
    position: 'absolute',
    shadowOffset: {
      width: 0,
      height: 0,
    },
    shadowOpacity: 0.8,
    shadowRadius: 8,
    elevation: 8,
  },
  wave1: {
    width: 180,
    height: 180,
    borderRadius: 90,
    borderWidth: 2,
    borderColor: 'rgba(137, 44, 220, 0.3)',
    position: 'absolute',
    shadowColor: '#892CDC',
    shadowOffset: {
      width: 0,
      height: 0,
    },
    shadowOpacity: 0.6,
    shadowRadius: 15,
    elevation: 15,
  },
  wave1Active: {
    borderColor: 'rgba(137, 44, 220, 0.8)',
    shadowOpacity: 1.0,
    shadowRadius: 35,
    elevation: 35,
  },
  wave2: {
    width: 160,
    height: 160,
    borderRadius: 80,
    borderWidth: 1.5,
    borderColor: 'rgba(137, 44, 220, 0.2)',
    position: 'absolute',
    shadowColor: '#892CDC',
    shadowOffset: {
      width: 0,
      height: 0,
    },
    shadowOpacity: 0.4,
    shadowRadius: 10,
    elevation: 10,
  },
  wave2Active: {
    borderColor: 'rgba(137, 44, 220, 0.6)',
    shadowOpacity: 0.9,
    shadowRadius: 30,
    elevation: 30,
  },
  wave3: {
    width: 140,
    height: 140,
    borderRadius: 70,
    borderWidth: 1,
    borderColor: 'rgba(137, 44, 220, 0.1)',
    position: 'absolute',
    shadowColor: '#892CDC',
    shadowOffset: {
      width: 0,
      height: 0,
    },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  wave3Active: {
    borderColor: 'rgba(137, 44, 220, 0.5)',
    shadowOpacity: 0.8,
    shadowRadius: 25,
    elevation: 25,
  },
  wave4: {
    width: 220,
    height: 220,
    borderRadius: 110,
    borderWidth: 1.5,
    borderColor: 'rgba(137, 44, 220, 0.2)',
    position: 'absolute',
    shadowColor: '#892CDC',
    shadowOffset: {
      width: 0,
      height: 0,
    },
    shadowOpacity: 0.3,
    shadowRadius: 20,
    elevation: 20,
  },
  wave5: {
    width: 260,
    height: 260,
    borderRadius: 130,
    borderWidth: 1,
    borderColor: 'rgba(137, 44, 220, 0.15)',
    position: 'absolute',
    shadowColor: '#892CDC',
    shadowOffset: {
      width: 0,
      height: 0,
    },
    shadowOpacity: 0.2,
    shadowRadius: 25,
    elevation: 25,
  },
  wave6: {
    width: 300,
    height: 300,
    borderRadius: 150,
    borderWidth: 0.8,
    borderColor: 'rgba(137, 44, 220, 0.1)',
    position: 'absolute',
    shadowColor: '#892CDC',
    shadowOffset: {
      width: 0,
      height: 0,
    },
    shadowOpacity: 0.15,
    shadowRadius: 30,
    elevation: 30,
  },
  titleContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  stepContainer: {
    gap: 8,
    marginBottom: 8,
  },
  reactLogo: {
    height: 178,
    width: 290,
    bottom: 0,
    left: 0,
    position: 'absolute',
  },
  statusContainer: {
    marginTop: 30,
    alignItems: 'center',
    gap: 10,
  },
  statusText: {
    fontSize: 16,
    fontWeight: '500',
    letterSpacing: 0.5,
  },
  reconnectButton: {
    backgroundColor: 'rgba(137, 44, 220, 0.2)',
    paddingHorizontal: 20,
    marginTop: 20,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: 'rgba(137, 44, 220, 0.4)',
  },
  reconnectText: {
    color: '#892CDC',
    fontSize: 14,
    fontWeight: '500',
  },
  svgContainer: {
    alignSelf: 'center',
    marginTop: -50, // Adjust this value to fine-tune vertical position
  },
});
