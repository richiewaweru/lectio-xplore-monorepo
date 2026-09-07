import { browser } from '$app/environment';

let online = $state(typeof navigator !== 'undefined' ? navigator.onLine : true);

if (browser && typeof window !== 'undefined') {
	const goOnline = () => {
		online = true;
	};
	const goOffline = () => {
		online = false;
	};
	window.addEventListener('online', goOnline);
	window.addEventListener('offline', goOffline);
}

export const connectivityStore = {
	get online() {
		return online;
	}
};
