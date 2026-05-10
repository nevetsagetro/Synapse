/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        serif: ['Lora', 'Georgia', 'serif']
      },
      colors: {
        ink: '#111827',
        paper: '#F8FAFC',
        amberAccent: '#F59E0B'
      }
    }
  },
  plugins: []
};
