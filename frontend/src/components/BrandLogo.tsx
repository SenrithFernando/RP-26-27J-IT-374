import logo from '../images/saferidelk.png';

type BrandLogoProps = {
  className?: string;
  decorative?: boolean;
};

export function BrandLogo({ className = 'h-12 w-12', decorative = false }: BrandLogoProps) {
  return (
    <img
      src={logo}
      alt={decorative ? '' : 'SafeRide-LK logo'}
      aria-hidden={decorative || undefined}
      className={`shrink-0 object-contain ${className}`}
    />
  );
}
