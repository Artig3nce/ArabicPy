import "./app.css";

export default function App() {
  return <main className="app" dir="rtl" style={{backgroundColor: "#ffffff"}}>
    <header>"الباء"</header>
    <section className="content"><input type="text" placeholder={"اكتب اسمك"} style={{"color": "#111827", "backgroundColor": "#ffffff"}} /></section>
    <nav><button>{"الرئيسية"}</button><button>{"البحث"}</button><button>{"التنبيهات"}</button><button>{"الرسائل"}</button></nav>
  </main>;
}
