import "./app.css";

export default function App() {
  return <main className="app" dir="rtl" style={{backgroundColor: "#ffffff"}}>
    <header>"الباء"</header>
    <section className="content"><p style={{"color": "#111827", "backgroundColor": "#ffffff"}}>{"ما هو اسمك"}</p><input type="text" placeholder={"اكتب اسمك"} style={{"color": "#111827", "backgroundColor": "#ffffff"}} /><p style={{"color": "#111827", "backgroundColor": "#ffffff"}}>{""}</p></section>
    <nav><button>{"الرئيسية"}</button><button>{"البحث"}</button><button>{"التنبيهات"}</button><button>{"الرسائل"}</button></nav>
  </main>;
}
