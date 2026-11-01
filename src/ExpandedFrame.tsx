// Same navigation frame in SkullKey and BoneCast; business components stay shared with QAM.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Focusable, DialogButton } from "@decky/ui";
const Button = DialogButton as any;
export type ExpandedSection = { id: string; label: string; icon?: ReactNode; color?: string };
// A marker beside the frame lets us remove only the surrounding Steam dialog
// chrome. Work in its owner document (the plugin window is not the modal window),
// and restore owned style changes when the view closes.
function DialogChrome() {
  const marker = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const changes: { element: HTMLElement; property: string; before: string; priority: string }[] = [];
    const paint = () => {
      const el = marker.current, win = el?.ownerDocument.defaultView;
      if (!el?.isConnected || !win) return;
      let parent = el.parentElement;
      for (let i = 0; parent && i < 12; i++, parent = parent.parentElement) {
        if (parent.getBoundingClientRect().width >= win.innerWidth * .98) break;
        for (const property of ["background", "box-shadow", "border"]) {
          if (changes.some(c => c.element === parent && c.property === property)) continue;
          changes.push({ element: parent, property, before: parent.style.getPropertyValue(property), priority: parent.style.getPropertyPriority(property) });
          parent.style.setProperty(property, property === "background" ? "transparent" : "none", "important");
        }
      }
    };
    paint();
    const timers = [300, 800].map(ms => setTimeout(paint, ms));
    return () => {
      timers.forEach(clearTimeout);
      for (const change of changes.reverse()) {
        const current = change.element.style.getPropertyValue(change.property);
        if (current !== (change.property === "background" ? "transparent" : "none")) continue;
        if (change.before) change.element.style.setProperty(change.property, change.before, change.priority);
        else change.element.style.removeProperty(change.property);
      }
    };
  }, []);
  return <div ref={marker} style={{ display: "none" }} />;
}
function Item({ section, active, onClick }: { section: ExpandedSection; active: boolean; onClick: () => void }) {
  const [focused, setFocused] = useState(false);
  return <Button noFocusRing onClick={onClick} onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
    onGamepadFocus={() => setFocused(true)} onGamepadBlur={() => setFocused(false)}
    style={{ display: "flex", alignItems: "center", gap: 10, width: "100%", margin: "3px 0", padding: "10px 12px",
      minWidth: 0, minHeight: 38, borderRadius: 8, color: "#fff", textAlign: "left", fontSize: 14,
      background: active ? (section.color || "#5865f2") : focused ? "#394452" : "transparent",
      boxShadow: focused ? "0 0 0 2px white" : "none" }}>
    {section.icon}<span style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{section.label}</span>
  </Button>;
}
export function ExpandedFrame({ brand, icon, sections, selected, onSelect, onClose, closeLabel, children }:
  { brand: string; icon: ReactNode; sections: ExpandedSection[]; selected: string; onSelect: (id: string) => void;
    onClose: () => void; closeLabel: string; children: ReactNode }) {
  const title = sections.find(s => s.id === selected)?.label || brand;
  return <><DialogChrome /><Focusable flow-children="row" className="necro-expanded" onScroll={(e: any) => { e.currentTarget.scrollTop = 0; }}
    style={{ display: "flex", width: "96vw", height: "min(80vh, calc(100vh - 160px))", marginLeft: "calc((100% - 96vw) / 2)",
      boxSizing: "border-box", overflow: "hidden", borderRadius: 12, color: "#f4f5f7", background: "#111820",
      boxShadow: "0 22px 60px #0008" }}>
    <style>{`.necro-expanded-side {width:240px;padding:14px;box-sizing:border-box;}
      .necro-expanded-body {padding:22px 24px;}
      @media(max-width:900px),(max-height:640px){.necro-expanded-side{width:190px;padding:9px;}
      .necro-expanded-body{padding:12px 14px;}}
      .necro-expanded-side::-webkit-scrollbar{display:none;}`}</style>
    <Focusable flow-children="column" className="necro-expanded-side"
      style={{ flexShrink: 0, minHeight: 0, overflow: "hidden", display: "flex", flexDirection: "column", background: "#202b34" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9, fontSize: 19, fontWeight: 800, padding: "8px 8px 17px", flexShrink: 0 }}>{icon}{brand}</div>
      <Focusable flow-children="column" className="necro-expanded-sections" style={{ flex: 1, minHeight: 0, overflowY: "auto", overflowX: "hidden", padding: 3 }}>
        {sections.map(s => <Item key={s.id} section={s} active={s.id === selected} onClick={() => onSelect(s.id)} />)}
      </Focusable>
      <div style={{ flexShrink: 0, paddingTop: 12 }}><Item section={{ id: "close", label: closeLabel }} active={false} onClick={onClose} /></div>
    </Focusable>
    <Focusable flow-children="column" className="necro-expanded-body" style={{ flex: 1, minWidth: 0, minHeight: 0, display: "flex", flexDirection: "column", overflow: "hidden", boxSizing: "border-box" }}>
      <div style={{ flexShrink: 0, fontSize: 23, fontWeight: 800, paddingBottom: 14, marginBottom: 12, borderBottom: "1px solid #ffffff18" }}>{title}</div>
      <div key={selected} style={{ flex: 1, minHeight: 0, overflowY: "auto", overflowX: "hidden", padding: 4 }}>{children}</div>
    </Focusable>
  </Focusable></>;
}
