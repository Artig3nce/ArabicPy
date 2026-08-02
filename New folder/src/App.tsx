import "./app.css";

export default function App() {
  return <main className="app" dir="rtl" style={{backgroundColor: "#FFFFFF"}}>
    <header>"الباء"</header>
    <section className="content"><p style={{"color": "#000000", "backgroundColor": "#F8FAFC"}}>{"ما هو اسمك"}</p><input type="text" placeholder={"اكتب اسمك"} style={{"color": "#000000", "backgroundColor": "#F8FAFC"}} /><p style={{"color": "#000000", "backgroundColor": "#F8FAFC"}}>{""}</p></section>
    <nav><button>{"الرئيسية"}</button><button>{"البحث"}</button><button>{"التنبيهات"}</button><button>{"الرسائل"}</button></nav>
  </main>;
}
