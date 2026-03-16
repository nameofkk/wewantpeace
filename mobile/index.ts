import { registerRootComponent } from 'expo';
import notifee, { EventType } from '@notifee/react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

import App from './App';

// Notifee 백그라운드 이벤트 핸들러 (알림 탭 처리)
notifee.onBackgroundEvent(async ({ type, detail }) => {
  if (type === EventType.PRESS && detail.notification?.data?.cluster_id) {
    const clusterId = detail.notification.data.cluster_id as string;
    if (clusterId !== 'test') {
      // pending URL 저장 → 앱이 active 되면 App.tsx에서 읽어서 네비게이션
      await AsyncStorage.setItem('@wwp_pending_notification', `/issues/${clusterId}`);
    }
  }
});

// registerRootComponent calls AppRegistry.registerComponent('main', () => App);
// It also ensures that whether you load the app in Expo Go or in a native build,
// the environment is set up appropriately
registerRootComponent(App);
