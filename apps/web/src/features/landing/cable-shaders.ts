export const cableVertexShader = /* glsl */ `
  uniform float uProgress;
  uniform float uMobile;
  uniform float uPointer;
  attribute float aStrand;
  varying vec3 vNormal;
  varying vec3 vPosition;
  varying vec2 vUv;
  varying float vStrand;
  const float PI = 3.14159265359;
  const float TAU = 6.28318530718;
  vec3 cablePoint(float t, float strand) {
    float connect = smoothstep(0.0, 1.0, uProgress);
    float trace = smoothstep(1.0, 2.0, uProgress);
    float inspect = smoothstep(2.1, 3.0, uProgress) * (1.0 - smoothstep(4.0, 4.8, uProgress));
    float loop = smoothstep(4.0, 5.0, uProgress);
    float angle = t * TAU * 3.0 + strand * TAU / 5.0;
    float ends = pow(abs(t - 0.5) * 2.0, 3.0);
    float radius = 0.18 + (1.0 - connect) * ends * 1.05;
    radius += inspect * pow(sin(t * PI), 6.0) * 0.62;
    float x = sin(t * TAU - 0.65) * mix(1.8, 0.65, trace);
    float y = (t - 0.5) * 6.0;
    float z = cos(t * TAU) * 0.42;
    vec3 open = vec3(x + cos(angle) * radius, y, z + sin(angle) * radius);
    float ring = t * TAU;
    vec3 closed = vec3(sin(ring) * (2.05 + cos(angle) * 0.18), cos(ring) * (2.35 + cos(angle) * 0.18), sin(angle) * 0.18 + sin(ring * 2.0) * 0.24);
    return mix(open, closed, loop);
  }
  void main() {
    float t = uv.x;
    float phi = uv.y * TAU;
    vec3 center = cablePoint(t, aStrand);
    vec3 tangent = normalize(cablePoint(t + 0.001, aStrand) - cablePoint(t - 0.001, aStrand));
    vec3 side = normalize(cross(tangent, vec3(0.0, 0.0, 1.0)));
    vec3 up = normalize(cross(side, tangent));
    vec3 normalDirection = cos(phi) * side + sin(phi) * up;
    vec3 point = center + normalDirection * 0.095;
    float turn = uPointer * 0.075;
    mat3 rotation = mat3(cos(turn), 0.0, -sin(turn), 0.0, 1.0, 0.0, sin(turn), 0.0, cos(turn));
    point = rotation * point;
    normalDirection = rotation * normalDirection;
    float transition = smoothstep(0.0, 0.9, uProgress);
    point *= mix(mix(0.78, 1.04, transition), 0.58, uMobile);
    point.y += mix(-2.35, uMobile * 2.8, transition);
    vec4 viewPosition = modelViewMatrix * vec4(point, 1.0);
    vNormal = normalize(normalMatrix * normalDirection);
    vPosition = viewPosition.xyz;
    vUv = uv;
    vStrand = aStrand;
    gl_Position = projectionMatrix * viewPosition;
  }
`;

export const cableFragmentShader = /* glsl */ `
  uniform float uProgress;
  uniform float uFocus;
  varying vec3 vNormal;
  varying vec3 vPosition;
  varying vec2 vUv;
  varying float vStrand;
  void main() {
    vec3 n = normalize(vNormal);
    vec3 viewDirection = normalize(-vPosition);
    vec3 light = normalize(vec3(-0.7, 1.1, 1.6));
    float diffuse = max(dot(n, light), 0.0);
    float sheen = pow(max(dot(reflect(-light, n), viewDirection), 0.0), 28.0);
    float edge = pow(1.0 - abs(dot(n, viewDirection)), 2.4);
    float studio = pow(abs(dot(n, normalize(vec3(0.8, 0.1, 1.0)))), 14.0);
    float weave = sin(vUv.x * 1700.0 + vUv.y * 38.0) * sin(vUv.x * 1700.0 - vUv.y * 38.0);
    float graphite = 0.008 + diffuse * 0.035 + edge * 0.10 + sheen * 0.9 + studio * 0.16 + weave * 0.003;
    float reversing = smoothstep(3.5, 4.0, uProgress) * (1.0 - smoothstep(4.8, 5.0, uProgress));
    float pulseAt = mix(fract(uProgress * 1.12 + 0.16), 1.0 - clamp(uProgress - 4.0, 0.0, 1.0), reversing);
    float signal = exp(-pow((vUv.x - pulseAt) * 45.0, 2.0));
    float signalStrength = smoothstep(0.8, 1.3, uProgress);
    float focused = 1.0 - smoothstep(0.0, 0.1, abs(uFocus - vStrand));
    graphite += signal * signalStrength * 0.46 + focused * 0.08;
    gl_FragColor = vec4(vec3(clamp(graphite, 0.015, 0.96)), 1.0);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

export const backgroundVertexShader = /* glsl */ `
  varying vec2 vUv;
  void main() { vUv = uv; gl_Position = vec4(position.xy, 0.999, 1.0); }
`;
export const backgroundFragmentShader = /* glsl */ `
  varying vec2 vUv;
  void main() {
    float grain = fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453);
    float edge = smoothstep(0.1, 0.9, distance(vUv, vec2(0.5, 0.55)));
    float paper = 0.986 - edge * 0.014 + (grain - 0.5) * 0.008;
    gl_FragColor = vec4(vec3(paper), 1.0);
  }
`;
