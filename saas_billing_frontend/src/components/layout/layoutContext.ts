import { createContext, useContext } from "react";

export interface LayoutContextValue {
  /** Opens the sidebar drawer (used on small screens). */
  openSidebar: () => void;
}

export const LayoutContext = createContext<LayoutContextValue>({
  openSidebar: () => {},
});

export function useLayout(): LayoutContextValue {
  return useContext(LayoutContext);
}
