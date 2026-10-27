---
name: Clinical Precision
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#45464d'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#76777d'
  outline-variant: '#c6c6cd'
  surface-tint: '#565e74'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#131b2e'
  on-primary-container: '#7c839b'
  inverse-primary: '#bec6e0'
  secondary: '#006a61'
  on-secondary: '#ffffff'
  secondary-container: '#86f2e4'
  on-secondary-container: '#006f66'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#271901'
  on-tertiary-container: '#98805d'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae2fd'
  primary-fixed-dim: '#bec6e0'
  on-primary-fixed: '#131b2e'
  on-primary-fixed-variant: '#3f465c'
  secondary-fixed: '#89f5e7'
  secondary-fixed-dim: '#6bd8cb'
  on-secondary-fixed: '#00201d'
  on-secondary-fixed-variant: '#005049'
  tertiary-fixed: '#fcdeb5'
  tertiary-fixed-dim: '#dec29a'
  on-tertiary-fixed: '#271901'
  on-tertiary-fixed-variant: '#574425'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  headline-xl:
    fontFamily: Geist
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-md:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.05em
  label-sm:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 48px
  container-max: 1280px
  gutter: 24px
---

## Brand & Style
The design system is anchored in the concept of "Clinical Precision." It balances the high-stakes reliability of pharmaceutical science with the forward-leaning innovation of modern medical technology. The target audience includes Medical Science Liaisons (MSLs) and Healthcare Professionals (HCPs) who require information density without cognitive overload.

The aesthetic follows a **Corporate / Modern** movement with a lean toward **Minimalism**. It prioritizes extreme legibility, intentional whitespace, and a systematic hierarchy. The UI should evoke a sense of calm authority, utilizing high-quality typography and a disciplined grid to ensure that complex medical data feels accessible and trustworthy.

## Colors
The palette is rooted in medical professionalism. 
- **Primary (Clinical Blue):** Used for navigation, high-level headers, and core brand elements to establish authority.
- **Secondary (Medical Teal):** Used for primary actions, progress indicators, and success states, reflecting innovation and health.
- **Background (Laboratory Gray):** A cool-toned neutral that reduces eye strain during long training sessions and provides a clean canvas for content.
- **Supportive Accents:** A soft Sky Blue is utilized for information callouts, while a disciplined scale of grays handles borders and secondary text.

## Typography
The system employs a dual-sans-serif approach to maximize both character and utility. **Geist** is used for headlines and labels to provide a technical, modern edge that appeals to MSLs and tech-savvy clinicians. **Inter** is used for all body copy and instructional text due to its exceptional readability in dense, data-heavy environments.

Heavy weighting is reserved for primary headings to create a clear "scan-path." Body text uses a generous 1.5x line-height to ensure medical terminology and complex phrasing remain digestible.

## Layout & Spacing
This design system utilizes a **Fluid Grid** model with a max-width container for desktop viewing. 
- **Desktop:** 12-column grid with 24px gutters and 48px side margins.
- **Tablet:** 8-column grid with 16px gutters and 24px side margins.
- **Mobile:** 4-column grid with 16px gutters and 16px side margins.

Spacing follows a strict 4pt linear scale. Generous vertical spacing (XL units) should be used between major sections to prevent the UI from feeling "crowded," which is a common pain point in medical software.

## Elevation & Depth
To maintain a "Shadcn-inspired" look, this design system avoids heavy shadows in favor of **low-contrast outlines** and **tonal layering**.

1.  **Level 0 (Background):** Laboratory Gray (#f8fafc).
2.  **Level 1 (Cards/Containers):** Pure White (#ffffff) with a 1px border in a soft Slate-200.
3.  **Level 2 (Popovers/Modals):** Pure White with a very subtle, highly diffused ambient shadow (0px 8px 30px rgba(15, 23, 42, 0.08)).

Interactive elements like buttons use a slight Y-axis shift on hover rather than an increase in shadow, maintaining a flat, professional profile.

## Shapes
The shape language is "Soft" (0.25rem/4px base radius). This subtle rounding offers a more modern and approachable feel than sharp corners while remaining more professional and "institutional" than fully rounded pill shapes. 

- **Small Components:** Checkboxes and small tags use the base 4px radius.
- **Standard Components:** Buttons and Input fields use the base 4px radius.
- **Large Components:** Course cards and Modal containers use a 0.5rem (8px) radius to create a softer visual containment for large blocks of content.

## Components
- **Buttons:** Primary buttons use Clinical Blue with white text. Secondary buttons use a Medical Teal outline. All buttons have a fixed height (40px for medium, 48px for large) and use Geist Medium for the label.
- **Input Fields:** Use a subtle 1px border (#e2e8f0). On focus, the border shifts to Medical Teal with a 2px outer "glow" (ring) in a 20% opacity teal.
- **Cards:** White background, 1px border, 8px corner radius. Header sections within cards should have a subtle bottom border to separate titles from content.
- **Chips/Badges:** Used for "Medical Category" or "Module Status." These should use a light tint of the status color (e.g., light teal background for "Completed") with dark teal text.
- **Lists:** High-density lists (e.g., drug monographs) should use alternating row highlights or clear dividers, with 12px vertical padding per item.
- **Progress Bars:** Use a thick 8px track for course progress, utilizing the Medical Teal for the fill color against a Slate-100 track.
- **Role Switcher:** A clean, segmented control to toggle between MSL (technical view) and HCP (clinical view) perspectives.