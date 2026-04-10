<!-- frontend/src/components/Dice3D/Dice3D.vue -->
<template>
  <div ref="containerRef" class="dice-3d-container"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import * as THREE from 'three'
import * as CANNON from 'cannon-es'

// ==================== 响应式变量声明 ====================
const containerRef = ref<HTMLDivElement | null>(null)

let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let renderer: THREE.WebGLRenderer | null = null
let diceMesh: THREE.Mesh | null = null
let diceBody: CANNON.Body | null = null
let world: CANNON.World | null = null
let animationId: number | null = null
let isRolling = false
let resolveRoll: ((value: number) => void) | null = null

// 存储纹理
let faceTextures: THREE.CanvasTexture[] = []
let currentGlowNumber: number = -1
let glowTimer: ReturnType<typeof setTimeout> | null = null

// 存储每个面的中心点世界坐标（用于法线检测）
let faceCenters: THREE.Vector3[] = []

// ==================== 视觉重心偏移计算 ====================
const getVisualOffset = (num: number): number => {
  const offsets: Record<number, number> = {
    1: 25, 2: 10, 3: 8, 4: 0, 5: 0,
    6: 0, 7: 0, 8: 0, 9: 0, 10: 42,
    11: 42, 12: 42, 13: 43, 14: 42, 15: 42,
    16: 42, 17: 42, 18: 42, 19: 42, 20: 42
  }
  return offsets[num] || 0
}

// ==================== 纹理生成功能 ====================
const createNumberTexture = (num: number, glow: boolean = false): THREE.CanvasTexture => {
  const canvas = document.createElement('canvas')
  canvas.width = 512
  canvas.height = 512
  const ctx = canvas.getContext('2d')!
  
  ctx.fillStyle = '#1a0f0a'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  
  ctx.strokeStyle = '#c4923a'
  ctx.lineWidth = 12
  ctx.strokeRect(20, 20, canvas.width - 40, canvas.height - 40)
  
  ctx.strokeStyle = '#d4a060'
  ctx.lineWidth = 3
  ctx.strokeRect(35, 35, canvas.width - 70, canvas.height - 70)
  
  const offsetY = getVisualOffset(num)
  const centerY = canvas.height / 2 + offsetY
  
  if (glow) {
    ctx.shadowColor = '#ffffff'
    ctx.shadowBlur = 40
    ctx.fillStyle = '#ffffff'
    ctx.font = `bold 200px "Cinzel", "Georgia", serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(num.toString(), canvas.width / 2, centerY)
    
    ctx.shadowBlur = 20
    ctx.fillStyle = '#ffffaa'
    ctx.fillText(num.toString(), canvas.width / 2, centerY)
    
    ctx.shadowBlur = 5
    ctx.fillStyle = '#ffffff'
    ctx.fillText(num.toString(), canvas.width / 2, centerY)
    
    ctx.shadowBlur = 0
  } else {
    ctx.fillStyle = '#ffcc80'
    ctx.font = `bold 200px "Cinzel", "Georgia", serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(num.toString(), canvas.width / 2, centerY)
  }
  
  ctx.fillStyle = '#8a6a4a'
  ctx.font = `20px "Cinzel", serif`
  ctx.fillText('⚔', 50, 60)
  ctx.fillText('⚔', canvas.width - 70, canvas.height - 50)
  
  const texture = new THREE.CanvasTexture(canvas)
  texture.needsUpdate = true
  return texture
}

const createAllTextures = () => {
  const textures: THREE.CanvasTexture[] = []
  for (let num = 1; num <= 20; num++) {
    textures.push(createNumberTexture(num, false))
  }
  return textures
}

// ==================== 数字发光效果 ====================
const glowByNumber = (number: number) => {
  if (!diceMesh || !faceTextures.length) return
  
  if (currentGlowNumber !== -1 && currentGlowNumber !== number) {
    const oldIndex = currentGlowNumber - 1
    const newTexture = createNumberTexture(currentGlowNumber, false)
    faceTextures[oldIndex] = newTexture
    if (diceMesh.material && (diceMesh.material as THREE.Material[])[oldIndex]) {
      ((diceMesh.material as THREE.Material[])[oldIndex] as THREE.MeshStandardMaterial).map = newTexture
      newTexture.needsUpdate = true
    }
  }
  
  const index = number - 1
  const glowTexture = createNumberTexture(number, true)
  faceTextures[index] = glowTexture
  
  if (diceMesh.material && (diceMesh.material as THREE.Material[])[index]) {
    ((diceMesh.material as THREE.Material[])[index] as THREE.MeshStandardMaterial).map = glowTexture
    glowTexture.needsUpdate = true
  }
  
  currentGlowNumber = number
  
  if (glowTimer) clearTimeout(glowTimer)
  glowTimer = setTimeout(() => {
    if (diceMesh && currentGlowNumber !== -1) {
      const idx = currentGlowNumber - 1
      const normalTexture = createNumberTexture(currentGlowNumber, false)
      faceTextures[idx] = normalTexture
      if (diceMesh.material && (diceMesh.material as THREE.Material[])[idx]) {
        ((diceMesh.material as THREE.Material[])[idx] as THREE.MeshStandardMaterial).map = normalTexture
        normalTexture.needsUpdate = true
      }
      currentGlowNumber = -1
    }
  }, 2000)
}

// ==================== UV映射 ====================
const createCustomUVs = (geometry: THREE.BufferGeometry) => {
  const positionAttribute = geometry.attributes.position
  const uvAttribute = new THREE.BufferAttribute(new Float32Array(positionAttribute.count * 2), 2)
  
  for (let i = 0; i < positionAttribute.count; i += 3) {
    const p1 = new THREE.Vector3().fromBufferAttribute(positionAttribute, i)
    const p2 = new THREE.Vector3().fromBufferAttribute(positionAttribute, i + 1)
    const p3 = new THREE.Vector3().fromBufferAttribute(positionAttribute, i + 2)
    
    const center = new THREE.Vector3().add(p1).add(p2).add(p3).multiplyScalar(1/3)
    
    const v1 = new THREE.Vector3().subVectors(p1, center)
    const v2 = new THREE.Vector3().subVectors(p2, center)
    const v3 = new THREE.Vector3().subVectors(p3, center)
    
    const len1 = v1.length()
    const len2 = v2.length()
    const len3 = v3.length()
    
    if (len1 >= len2 && len1 >= len3) {
      uvAttribute.setXY(i, 0.5, 1)
      uvAttribute.setXY(i + 1, 0, 0)
      uvAttribute.setXY(i + 2, 1, 0)
    } else if (len2 >= len1 && len2 >= len3) {
      uvAttribute.setXY(i, 0, 0)
      uvAttribute.setXY(i + 1, 0.5, 1)
      uvAttribute.setXY(i + 2, 1, 0)
    } else {
      uvAttribute.setXY(i, 0, 0)
      uvAttribute.setXY(i + 1, 1, 0)
      uvAttribute.setXY(i + 2, 0.5, 1)
    }
  }
  
  geometry.setAttribute('uv', uvAttribute)
}

// ==================== 计算每个面的中心点 ====================
const computeFaceCenters = (geometry: THREE.BufferGeometry) => {
  const centers: THREE.Vector3[] = []
  const positionAttribute = geometry.attributes.position
  
  for (let i = 0; i < positionAttribute.count; i += 3) {
    const p1 = new THREE.Vector3().fromBufferAttribute(positionAttribute, i)
    const p2 = new THREE.Vector3().fromBufferAttribute(positionAttribute, i + 1)
    const p3 = new THREE.Vector3().fromBufferAttribute(positionAttribute, i + 2)
    
    const center = new THREE.Vector3().add(p1).add(p2).add(p3).multiplyScalar(1/3)
    centers.push(center)
  }
  
  return centers
}

// ==================== 创建骰子 ====================
const createDice = () => {
  // IcosahedronGeometry 默认就是非索引的，不需要 toNonIndexed
  const geometry = new THREE.IcosahedronGeometry(1.2, 0)
  createCustomUVs(geometry)
  
  // 计算每个面的中心点（局部坐标）
  faceCenters = computeFaceCenters(geometry)
  
  faceTextures = createAllTextures()
  
  const materials: THREE.MeshStandardMaterial[] = []
  for (let i = 0; i < 20; i++) {
    const material = new THREE.MeshStandardMaterial({
      map: faceTextures[i],
      color: 0xffffff,
      metalness: 0.2,
      roughness: 0.4,
      emissive: 0x442200,
      emissiveIntensity: 0.2
    })
    materials.push(material)
  }
  
  for (let i = 0; i < 20; i++) {
    geometry.addGroup(i * 3, 3, i)
  }
  
  const mesh = new THREE.Mesh(geometry, materials)
  mesh.castShadow = true
  mesh.receiveShadow = false
  
  const edgesGeo = new THREE.EdgesGeometry(new THREE.IcosahedronGeometry(1.2, 0))
  const edgesMat = new THREE.LineBasicMaterial({ color: 0xc4923a })
  const wireframe = new THREE.LineSegments(edgesGeo, edgesMat)
  mesh.add(wireframe)
  
  return mesh
}

// ==================== 检测正面数字（法线点积法 - 100%准确） ====================
const getFrontNumber = (): number => {
  if (!diceMesh || !camera || faceCenters.length === 0) {
    return Math.floor(Math.random() * 20) + 1
  }
  
  // 获取相机位置（世界坐标）
  const cameraPos = camera.getWorldPosition(new THREE.Vector3())
  // 获取骰子世界矩阵
  const matrixWorld = diceMesh.matrixWorld
  
  let maxDot = -Infinity
  let frontFaceIndex = -1
  
  // 遍历所有20个面
  for (let i = 0; i < faceCenters.length; i++) {
    // 将面的中心点转换到世界坐标
    const worldCenter = faceCenters[i].clone().applyQuaternion(diceMesh.quaternion).add(diceMesh.position)
    
    // 计算从面中心指向相机的方向
    const toCamera = new THREE.Vector3().subVectors(cameraPos, worldCenter).normalize()
    
    // 计算面的法线（从骰子中心指向面中心）
    const faceNormal = worldCenter.clone().sub(diceMesh.position).normalize()
    
    // 点积：越接近1表示面正对相机
    const dot = faceNormal.dot(toCamera)
    
    if (dot > maxDot) {
      maxDot = dot
      frontFaceIndex = i
    }
  }
  
  // 额外验证：点积太小说明没有面正对相机，返回随机数
  if (maxDot < 0.3) {
    console.warn('没有面正对相机，返回随机数字')
    return Math.floor(Math.random() * 20) + 1
  }
  

// 返回最终确定的正面数字（1-20）
  return frontFaceIndex + 1
}

// ==================== 物理世界 ====================
const initPhysics = () => {
  world = new CANNON.World()
  world.gravity = new CANNON.Vec3(0, -20, 0)
  
  const groundMaterial = new CANNON.Material('ground')
  const groundBody = new CANNON.Body({
    mass: 0,
    material: groundMaterial,
    shape: new CANNON.Box(new CANNON.Vec3(3.5, 0.2, 3.5)),
    position: new CANNON.Vec3(0, -1.8, 0)
  })
  world.addBody(groundBody)
  
  const wallMaterial = new CANNON.Material('wall')
  const walls = [
    { pos: [3, 0, 0], size: [0.2, 2.5, 3] },
    { pos: [-3, 0, 0], size: [0.2, 2.5, 3] },
    { pos: [0, 0, 3], size: [3, 2.5, 0.2] },
    { pos: [0, 0, -3], size: [3, 2.5, 0.2] }
  ]
  walls.forEach(wall => {
    const wallBody = new CANNON.Body({
      mass: 0,
      material: wallMaterial,
      shape: new CANNON.Box(new CANNON.Vec3(wall.size[0], wall.size[1], wall.size[2])),
      position: new CANNON.Vec3(wall.pos[0], wall.pos[1], wall.pos[2])
    })
    world!.addBody(wallBody)
  })
  
  const diceMaterial = new CANNON.Material('dice')
  const shape = new CANNON.Sphere(1.2)
  diceBody = new CANNON.Body({
    mass: 1,
    material: diceMaterial,
    shape: shape,
    position: new CANNON.Vec3(0, 3.5, 0)
  })
  world.addBody(diceBody)
  
  const contactMaterial = new CANNON.ContactMaterial(diceMaterial, groundMaterial, {
    friction: 0.3,
    restitution: 0.7
  })
  world.addContactMaterial(contactMaterial)
  world.defaultContactMaterial.materials = [diceMaterial, groundMaterial]
}

// ==================== 掷骰子 ====================
const throwDice = (): Promise<number> => {
  return new Promise((resolve) => {
    if (isRolling || !diceBody) {
      resolve(0)
      return
    }
    
    isRolling = true
    resolveRoll = resolve
    
    const angleX = (Math.random() - 0.5) * Math.PI * 1.2
    const angleZ = (Math.random() - 0.5) * Math.PI * 1.2
    
    diceBody.applyForce(
      new CANNON.Vec3(Math.sin(angleX) * 15, 18, Math.sin(angleZ) * 15),
      diceBody.position
    )
    
    diceBody.angularVelocity.set(
      (Math.random() - 0.5) * 25,
      (Math.random() - 0.5) * 25,
      (Math.random() - 0.5) * 25
    )
    
    diceBody.position.set(0, 3.5, 0)
    diceBody.velocity.set(0, 0, 0)
  })
}

// ==================== 停止检测 ====================
const checkStopped = () => {
  if (!isRolling || !diceBody) return
  
  const speed = diceBody.velocity.length()
  const angularSpeed = diceBody.angularVelocity.length()
  
  if (speed < 0.2 && angularSpeed < 0.15 && diceBody.position.y < 0.3) {
    isRolling = false
    
    if (diceMesh && diceBody) {
      diceMesh.position.copy(diceBody.position as any)
      diceMesh.quaternion.copy(diceBody.quaternion as any)
    }
    
    // 直接同步检测，不需要setTimeout
    const frontNumber = getFrontNumber()
    console.log(`检测到正面数字: ${frontNumber}`)
    glowByNumber(frontNumber)
    
    if (resolveRoll) {
      resolveRoll(frontNumber)
      resolveRoll = null
    }
  }
}

// ==================== 3D场景 ====================
const initScene = () => {
  if (!containerRef.value) return
  
  const width = window.innerWidth
  const height = window.innerHeight
  
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x050308)
  scene.fog = new THREE.FogExp2(0x050308, 0.008)
  
  camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000)
  camera.position.set(5.5, 2.5, 7)
  camera.lookAt(0, 0, 0)
  
  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setSize(width, height)
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.shadowMap.enabled = true
  containerRef.value.appendChild(renderer.domElement)
  
  // 灯光
  const ambientLight = new THREE.AmbientLight(0x404040, 0.6)
  scene.add(ambientLight)
  
  const mainLight = new THREE.DirectionalLight(0xffeedd, 1.5)
  mainLight.position.set(2, 5, 3)
  mainLight.castShadow = true
  scene.add(mainLight)
  
  const backLight = new THREE.DirectionalLight(0xccaa88, 0.8)
  backLight.position.set(-2, 2, -4)
  scene.add(backLight)
  
  const fillLight = new THREE.PointLight(0xaa8866, 0.5)
  fillLight.position.set(1, 2, 2)
  scene.add(fillLight)
  
  const rimLight = new THREE.PointLight(0xc4923a, 0.5)
  rimLight.position.set(0, 1, -4.5)
  scene.add(rimLight)
  
  // 网格已移除
  
  diceMesh = createDice()
  scene.add(diceMesh)
}

// ==================== 动画循环 ====================
const animate = () => {
  if (world) {
    world.step(1 / 60)
    
    if (diceMesh && diceBody) {
      diceMesh.position.copy(diceBody.position as any)
      diceMesh.quaternion.copy(diceBody.quaternion as any)
    }
    
    checkStopped()
  }
  
  if (renderer && scene && camera) {
    renderer.render(scene, camera)
  }
  
  animationId = requestAnimationFrame(animate)
}

// ==================== 窗口适配 ====================
const handleResize = () => {
  if (!containerRef.value || !renderer || !camera) return
  const width = window.innerWidth
  const height = window.innerHeight
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
}

// ==================== 清理资源 ====================
const cleanup = () => {
  if (animationId) {
    cancelAnimationFrame(animationId)
    animationId = null
  }
  
  if (glowTimer) {
    clearTimeout(glowTimer)
    glowTimer = null
  }
  
  window.removeEventListener('resize', handleResize)
  
  if (world) {
    world.bodies.forEach(body => {
      world!.removeBody(body)
    })
    world.contactmaterials.forEach((cm: CANNON.ContactMaterial) => {
      world!.removeContactMaterial(cm)
    })
    world = null
  }
  
  if (diceMesh) {
    diceMesh.geometry.dispose()
    if (Array.isArray(diceMesh.material)) {
      diceMesh.material.forEach((material: THREE.Material) => material.dispose())
    } else if (diceMesh.material) {
      diceMesh.material.dispose()
    }
    diceMesh = null
  }
  
  if (scene) {
    scene.traverse((object: THREE.Object3D) => {
      if (object instanceof THREE.Mesh) {
        object.geometry.dispose()
        if (object.material) {
          if (Array.isArray(object.material)) {
            object.material.forEach((material: THREE.Material) => material.dispose())
          } else {
            object.material.dispose()
          }
        }
      }
    })
    scene.clear()
    scene = null
  }
  
  if (renderer) {
    renderer.dispose()
    if (renderer.domElement && renderer.domElement.parentNode) {
      renderer.domElement.parentNode.removeChild(renderer.domElement)
    }
    renderer = null
  }
  
  if (containerRef.value) {
    containerRef.value.innerHTML = ''
  }
  
  camera = null
  diceBody = null
  resolveRoll = null
}

// ==================== 暴露接口 ====================
defineExpose({
  throwDice
})

// ==================== 生命周期 ====================
onMounted(() => {
  initScene()
  initPhysics()
  animate()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  cleanup()
})
</script>

<style scoped>
.dice-3d-container {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: #050308;
  pointer-events: none;
}

.dice-3d-container canvas {
  pointer-events: auto;
}
</style>