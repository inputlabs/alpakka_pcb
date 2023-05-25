# PCB generations

The concept of `Generation` versioning was introduced to mark minor changes that are still relevant for the firmware execution, so the firmware can use different configuration values or execution paths if needed.

This way a single unified version of the firmware is able to support multiple versions of the PCB if the changes are not big backward compatibility breakers.

These firmware-relevant changes may be different in size and complexity than the actual changes in PCB layout or components, and therefore are tracked separately from the main PCB semantic versioning.

## Generations

| Generation  | From PCB version | To PCB version | FW-relevant change |
| - | - | - | - |
| 0  | b0.0.0 | b0.84.4 | |
| 1  | b0.88.0 | ONGOING | 100KΩ -> 500KΩ touch resistor |

## Masking

The firmware can check in execution-time to which generation the PCB belongs via a ternary mask on the first IO expander unused pins.

| Electrical | Ternary value |
| - | - |
| FLOAT | 0 |
| GND | 1 |
| VCC | 2 |

| Ternary mask index | 3 | 2 | 1 | 0 |
| - | - | - | - | - |
| **Pin** | - | - | A10 | A11 |

| Generation  | A10 | A11 |
| - | - | - |
| 0 | FLOAT | FLOAT |
| 1 | FLOAT | GND |
