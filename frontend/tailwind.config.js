/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        pastel: {
          bg: '#F7F8FC',
          surface: '#FFFFFF',
          subtle: '#F2F5F8',
          text: '#26313F',
          muted: '#6E7785',
          border: '#E7EAF0',
          teal: '#72C9BE',
          'teal-dark': '#3D8C82',
          mint: '#CFEDE7',
          blue: '#B7D4F4',
          lavender: '#D4C8F4',
          sage: '#CADFCB',
          peach: '#F4D5C2',
          amber: '#F3DFAB',
          rose: '#EABFC5',
        },
        medteal: {
          50: '#F0FDFA',
          100: '#CCFBF1',
          200: '#99F6E4',
          300: '#5EEAD4',
          400: '#2DD4BF',
          500: '#72C9BE',
          600: '#5AB8AC',
          700: '#3D8C82',
          800: '#2A635C',
          900: '#183B37',
        },
      },
      boxShadow: {
        soft: '0 2px 8px rgba(38, 49, 63, 0.04)',
        card: '0 4px 20px rgba(38, 49, 63, 0.04)',
        float: '0 12px 32px rgba(38, 49, 63, 0.08)',
      },
      borderRadius: {
        '2xl': '18px',
        '3xl': '24px',
      }
    },
  },
  plugins: [],
}
