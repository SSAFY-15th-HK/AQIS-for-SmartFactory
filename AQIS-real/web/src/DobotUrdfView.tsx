import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { ColladaLoader } from "three/examples/jsm/loaders/ColladaLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

type DobotJoint = {
  name: string;
  position_rad: number;
  position_deg: number;
};

type DobotStatus = {
  joints?: DobotJoint[];
  tcp_pose?: { x: number; y: number; z: number; yaw: number };
  alarms?: number[];
  gripper_status?: string;
  stamp?: number;
};

type UrdfJoint = {
  name: string;
  axis: THREE.Vector3;
  originPosition: THREE.Vector3;
  originRotation: THREE.Euler;
  group: THREE.Group;
  mimic?: { joint: string; multiplier: number; offset: number };
};

type Props = {
  status: DobotStatus;
};

const URDF_URL = "/dobot/magician.urdf";
const ROS_TO_THREE = new THREE.Matrix4().makeRotationX(-Math.PI / 2);
const THREE_TO_ROS = new THREE.Matrix4().makeRotationX(Math.PI / 2);
const HOME_CAMERA_POSITION = new THREE.Vector3(0.48, 0.46, 0.74);
const HOME_CAMERA_TARGET = new THREE.Vector3(0.03, 0.15, 0.02);
const INITIAL_JOINT_POSE_RAD = new Map<string, number>([
  ["magician_joint_1", 0],
  ["magician_joint_2", 0],
  ["magician_joint_3", 0],
  ["magician_joint_4", 0],
]);

function numbers(value: string | null, fallback: [number, number, number] = [0, 0, 0]): [number, number, number] {
  if (!value) return fallback;
  const parsed = value.trim().split(/\s+/).map(Number);
  return [
    Number.isFinite(parsed[0]) ? parsed[0] : fallback[0],
    Number.isFinite(parsed[1]) ? parsed[1] : fallback[1],
    Number.isFinite(parsed[2]) ? parsed[2] : fallback[2],
  ];
}

function firstElement(parent: Element, selector: string): Element | null {
  return parent.querySelector(selector);
}

function rosVectorToThree(value: [number, number, number]) {
  return new THREE.Vector3(value[0], value[1], value[2]).applyMatrix4(ROS_TO_THREE);
}

function rosRotationToThree(rpy: [number, number, number]) {
  const rosRotation = new THREE.Matrix4().makeRotationFromEuler(new THREE.Euler(rpy[0], rpy[1], rpy[2], "XYZ"));
  const threeRotation = new THREE.Matrix4().multiplyMatrices(ROS_TO_THREE, rosRotation).multiply(THREE_TO_ROS);
  return new THREE.Euler().setFromRotationMatrix(threeRotation, "XYZ");
}

function applyUrdfTransform(object: THREE.Object3D, xyz: [number, number, number], rpy: [number, number, number]) {
  object.position.copy(rosVectorToThree(xyz));
  object.rotation.copy(rosRotationToThree(rpy));
}

function prepareMeshMaterials(object: THREE.Object3D) {
  object.traverse((child) => {
    const mesh = child as THREE.Mesh;
    if (!mesh.isMesh) return;
    mesh.castShadow = true;
    mesh.receiveShadow = true;

    const prepare = (source: THREE.Material) => {
      const material = source.clone();
      if (material instanceof THREE.MeshStandardMaterial || material instanceof THREE.MeshPhongMaterial) {
        material.color.r = Math.min(material.color.r, 1);
        material.color.g = Math.min(material.color.g, 1);
        material.color.b = Math.min(material.color.b, 1);
        material.side = THREE.DoubleSide;
      }
      return material;
    };

    mesh.material = Array.isArray(mesh.material) ? mesh.material.map(prepare) : prepare(mesh.material);
  });
}

function removeImportedSceneHelpers(object: THREE.Object3D) {
  const removable: THREE.Object3D[] = [];
  object.traverse((child) => {
    if (child instanceof THREE.Light || child instanceof THREE.Camera) {
      removable.push(child);
    }
  });
  removable.forEach((child) => child.parent?.remove(child));
}

function jointName(name: string) {
  if (name.includes("joint_1")) return "magician_joint_1";
  if (name.includes("joint_2")) return "magician_joint_2";
  if (name.includes("joint_3")) return "magician_joint_3";
  if (name.includes("joint_4")) return "magician_joint_4";
  return name;
}

export function DobotUrdfView({ status }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const jointsRef = useRef<Map<string, UrdfJoint>>(new Map());
  const sceneRootRef = useRef<THREE.Group | null>(null);
  const alarmRef = useRef(false);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.NoToneMapping;
    renderer.shadowMap.enabled = true;
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#050505");

    const camera = new THREE.PerspectiveCamera(42, 1, 0.01, 8);
    camera.position.copy(HOME_CAMERA_POSITION);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.copy(HOME_CAMERA_TARGET);
    controls.enableDamping = true;
    controls.minDistance = 0.35;
    controls.maxDistance = 2.4;
    controls.saveState();

    scene.add(new THREE.HemisphereLight("#f2f2ee", "#151515", 1.35));
    const keyLight = new THREE.DirectionalLight("#ffffff", 2.4);
    keyLight.position.set(1.4, -1.2, 1.8);
    keyLight.castShadow = true;
    scene.add(keyLight);
    const rimLight = new THREE.DirectionalLight("#ff6a2a", 1.1);
    rimLight.position.set(-1.2, 0.8, 1.0);
    scene.add(rimLight);

    const floor = new THREE.Mesh(
      new THREE.CircleGeometry(0.42, 64),
      new THREE.MeshStandardMaterial({ color: "#090909", roughness: 0.95, metalness: 0.1 }),
    );
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    scene.add(floor);

    const axes = new THREE.GridHelper(0.9, 12, "#ff5a1f", "#252525");
    axes.position.y = -0.001;
    scene.add(axes);

    const root = new THREE.Group();
    sceneRootRef.current = root;
    scene.add(root);

    const resize = () => {
      const { width, height } = container.getBoundingClientRect();
      renderer.setSize(width, height, false);
      camera.aspect = width / Math.max(height, 1);
      camera.updateProjectionMatrix();
    };
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(container);
    resize();

    let disposed = false;
    const colladaLoader = new ColladaLoader();

    async function loadMesh(url: string): Promise<THREE.Object3D> {
      const collada = await colladaLoader.loadAsync(url);
      if (!collada) {
        throw new Error(`Failed to load Dobot mesh: ${url}`);
      }
      const object = collada.scene;
      object.scale.setScalar(1);
      removeImportedSceneHelpers(object);
      prepareMeshMaterials(object);
      return object;
    }

    async function loadRobot() {
      setLoadError("");
      const urdf = await fetch(URDF_URL).then((response) => response.text());
      if (disposed) return;

      const doc = new DOMParser().parseFromString(urdf, "application/xml");
      const linkGroups = new Map<string, THREE.Group>();
      const linkNodes = Array.from(doc.querySelectorAll("robot > link"));

      for (const linkNode of linkNodes) {
        const linkName = linkNode.getAttribute("name");
        if (!linkName) continue;
        const linkGroup = new THREE.Group();
        linkGroup.name = linkName;
        linkGroups.set(linkName, linkGroup);

        const visual = firstElement(linkNode, "visual");
        const mesh = firstElement(linkNode, "visual geometry mesh");
        const filename = mesh?.getAttribute("filename");
        if (filename) {
          const visualGroup = new THREE.Group();
          const origin = firstElement(visual ?? linkNode, "origin");
          const xyz = numbers(origin?.getAttribute("xyz") ?? null);
          const rpy = numbers(origin?.getAttribute("rpy") ?? null);
          applyUrdfTransform(visualGroup, xyz, rpy);
          visualGroup.add(await loadMesh(filename));
          linkGroup.add(visualGroup);
        }
      }

      const jointNodes = Array.from(doc.querySelectorAll("robot > joint"));
      const childLinks = new Set<string>();

      for (const jointNode of jointNodes) {
        const name = jointNode.getAttribute("name");
        const parent = firstElement(jointNode, "parent")?.getAttribute("link");
        const child = firstElement(jointNode, "child")?.getAttribute("link");
        if (!name || !parent || !child) continue;

        const parentGroup = linkGroups.get(parent);
        const childGroup = linkGroups.get(child);
        if (!parentGroup || !childGroup) continue;

        const jointGroup = new THREE.Group();
        jointGroup.name = name;
        const origin = firstElement(jointNode, "origin");
        const xyz = numbers(origin?.getAttribute("xyz") ?? null);
        const rpy = numbers(origin?.getAttribute("rpy") ?? null);
        applyUrdfTransform(jointGroup, xyz, rpy);
        jointGroup.add(childGroup);
        parentGroup.add(jointGroup);
        childLinks.add(child);

        const axis = numbers(firstElement(jointNode, "axis")?.getAttribute("xyz") ?? null, [0, 0, 1]);
        const axisVector = rosVectorToThree(axis).normalize();
        const mimicNode = firstElement(jointNode, "mimic");
        jointsRef.current.set(name, {
          name,
          axis: axisVector,
          originPosition: rosVectorToThree(xyz),
          originRotation: rosRotationToThree(rpy),
          group: jointGroup,
          mimic: mimicNode
            ? {
                joint: mimicNode.getAttribute("joint") ?? "",
                multiplier: Number(mimicNode.getAttribute("multiplier") ?? 1),
                offset: Number(mimicNode.getAttribute("offset") ?? 0),
              }
            : undefined,
        });
      }

      const rootLink = linkGroups.get("magician_root_link") ?? [...linkGroups.entries()].find(([name]) => !childLinks.has(name))?.[1];
      if (rootLink) root.add(rootLink);
    }

    loadRobot().catch((error: unknown) => {
      if (!disposed) {
        setLoadError(error instanceof Error ? error.message : "Failed to load Dobot model");
      }
    });

    let frame = 0;
    const animate = () => {
      frame = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      controls.dispose();
      renderer.dispose();
      renderer.domElement.remove();
      scene.traverse((object) => {
        const mesh = object as THREE.Mesh;
        if (mesh.geometry) mesh.geometry.dispose();
        if (mesh.material) {
          const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
          materials.forEach((material) => material.dispose());
        }
      });
      jointsRef.current.clear();
      sceneRootRef.current = null;
    };
  }, []);

  useEffect(() => {
    const values = new Map<string, number>();
    for (const joint of status.joints ?? []) {
      values.set(joint.name, joint.position_rad);
      values.set(jointName(joint.name), joint.position_rad);
    }

    jointsRef.current.forEach((joint, name) => {
      const sourceName = joint.mimic?.joint ?? name;
      const source = values.get(sourceName) ?? INITIAL_JOINT_POSE_RAD.get(sourceName) ?? INITIAL_JOINT_POSE_RAD.get(jointName(sourceName));
      const angle = (source ?? 0) * (joint.mimic?.multiplier ?? 1) + (joint.mimic?.offset ?? 0);
      joint.group.position.copy(joint.originPosition);
      joint.group.rotation.copy(joint.originRotation);
      joint.group.rotateOnAxis(joint.axis, angle);
    });
  }, [status.joints]);

  useEffect(() => {
    alarmRef.current = Boolean(status.alarms?.length);
  }, [status.alarms]);

  return (
    <div className={`dobotViewport ${status.alarms?.length ? "alarmed" : ""}`} ref={containerRef}>
      {loadError ? (
        <div className="modelOverlay error">{loadError}</div>
      ) : (
        !status.stamp && <div className="modelOverlay">Waiting for Dobot topics</div>
      )}
      {status.alarms?.length ? <div className="modelBadge danger">Alarm</div> : <div className="modelBadge ok">Suction Cup</div>}
    </div>
  );
}
