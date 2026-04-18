import { initializeApp } from 'firebase/app'
import { connectAuthEmulator, getAuth, GoogleAuthProvider } from 'firebase/auth'

// In local dev with the Firebase emulator, the production config values
// aren't required — a fake project id is enough. VITE_USE_FIREBASE_EMULATOR
// flips the app to emulator mode.
const useEmulator = import.meta.env.VITE_USE_FIREBASE_EMULATOR === 'true'

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || 'fake-api-key',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || 'localhost',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || 'ielts-bot-dev',
}

const app = initializeApp(firebaseConfig)
export const auth = getAuth(app)
export const googleProvider = new GoogleAuthProvider()

if (useEmulator) {
  const host =
    import.meta.env.VITE_FIREBASE_AUTH_EMULATOR_URL || 'http://localhost:9099'
  connectAuthEmulator(auth, host, { disableWarnings: true })

  console.info('[firebase] Using Auth emulator at', host)
}
