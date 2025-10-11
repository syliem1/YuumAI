/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,jsx}",
    "./components/**/*.{js,jsx}"
  ],
  theme: {
    extend: {
      colors: {
        primary: "#78BCB0",
        accent: "B99758",
        background: "F4EAEA",
        dark: "56374E",
      },
    },
  },
  plugins: [],
}
