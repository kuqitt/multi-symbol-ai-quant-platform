export default {
    darkMode: "class",
    content: ["./index.html", "./src/**/*.{ts,tsx}"],
    theme: {
        extend: {
            colors: {
                ink: "#0f172a",
                shell: "#f8fafc",
                card: "#ffffff",
                accent: "#0f766e",
                danger: "#b91c1c",
                warning: "#d97706",
            },
            boxShadow: {
                panel: "0 16px 40px rgba(15, 23, 42, 0.10)",
            },
        },
    },
    plugins: [],
};
